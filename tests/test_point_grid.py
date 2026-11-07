from datetime import date, time
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest

from courseflow import service
from courseflow.group import BusyCard, decode_card
from courseflow.model import Course, Timetable


def member():
    return BusyCard("不能外发的成员名字", date(2026, 9, 7), {1: {0, 3, 9}},
                    {3: (time(10), time(10, 45)), 4: (time(10, 50), time(11, 35))}, "UTC+8")


def defaults_in(html):
    return json.loads(re.search(r'<script id="courseflow-defaults" type="application/json">(.*?)</script>', html).group(1))


class SharedPointGridTests(unittest.TestCase):
    def test_share_without_personal_timetable_uses_members_and_keeps_private_data_out(self):
        card = member()
        own = Timetable(courses=[Course("不应外发的课名", 0, 1, 2, "私有教室", "1-16周")])
        before = service.point_grid_path().read_bytes()
        with TemporaryDirectory() as folder:
            path = service.export_point_grid(Path(folder) / "分享页.html", own, [card], 7)
            html = path.read_text(encoding="utf-8")
        self.assertEqual(defaults_in(html), {
            "start": "2026-09-07", "week": 7, "timezone": "UTC+8",
            "period_times": {"3": "10:00-10:45", "4": "10:50-11:35"},
        })
        for private in (card.name, card.encode(), "不应外发的课名", "私有教室"):
            self.assertNotIn(private, html)
        self.assertEqual(service.point_grid_path().read_bytes(), before)
        self.assertNotRegex(html, r'(?:src|href)=["\']https?://')

    def test_empty_context_leaves_semester_date_for_the_recipient_to_confirm(self):
        defaults = service.point_grid_defaults(Timetable(), [], "7")
        self.assertEqual((defaults["start"], defaults["week"], defaults["period_times"]), ("", 7, {}))

    def test_invalid_week_or_inconsistent_member_clocks_cannot_create_a_page(self):
        first = member()
        second = member()
        second.name = "另一位成员"
        second.period_times = {3: (time(9), time(9, 45))}
        with TemporaryDirectory() as folder:
            path = Path(folder) / "page.html"
            for week in (0, 105, True, "not-a-week"):
                with self.assertRaises(ValueError):
                    service.export_point_grid(path, members=[first], week=week)
                self.assertFalse(path.exists())
            with self.assertRaisesRegex(ValueError, "作息不一致"):
                service.export_point_grid(path, members=[first, second])
            self.assertFalse(path.exists())

    def test_point_grid_export_cannot_overwrite_a_timetable_file(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "课表.yaml"
            path.write_bytes(b"existing source")
            with self.assertRaises(ValueError):
                service.export_point_grid(path)
            self.assertEqual(path.read_bytes(), b"existing source")

    @unittest.skipUnless(shutil.which("node"), "Node is needed to exercise the offline page script")
    def test_exported_file_without_query_string_generates_a_roundtrippable_card(self):
        with TemporaryDirectory() as folder:
            path = service.export_point_grid(Path(folder) / "page.html", members=[member()], week=7)
            html = path.read_text(encoding="utf-8")
        bootstrap = re.search(r'<script id="courseflow-defaults" type="application/json">(.*?)</script>', html).group(1)
        codec = re.search(r'<script id="card-codec">([\s\S]*?)</script>', html).group(1)
        script = re.findall(r'<script>([\s\S]*?)</script>', html)[0]
        harness = r'''
class Element {
  constructor(){this.value="";this.textContent="";this.checked=false;this.disabled=false;this.style={};this.attrs={};this.events={};this.children=[];}
  appendChild(child){this.children.push(child);return child;}
  setAttribute(key,value){this.attrs[key]=value;}
  addEventListener(name,handler){this.events[name]=handler;}
  click(){if(!this.disabled&&this.events.click)this.events.click();}
  scrollIntoView(){}
}
const elements=new Map();
globalThis.window=globalThis;
globalThis.location={search:""};
globalThis.document={getElementById(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id);},createElement(){return new Element();}};
document.getElementById("pairs").checked=true;
document.getElementById("generate").disabled=true;
'''
        harness += "document.getElementById('courseflow-defaults').textContent=" + json.dumps(bootstrap) + ";\n"
        actions = r'''
document.getElementById("name").value="外部成员";
const cell=document.getElementById("grid").children.find(item=>item.attrs["aria-label"]==="周二第3节");
cell.click();
const confirm=document.getElementById("confirmed");confirm.checked=true;confirm.events.change();
document.getElementById("generate").click();
console.log(document.getElementById("code").value);
'''
        result = subprocess.run([shutil.which("node"), "-"], input=harness + codec + script + actions,
                                text=True, encoding="utf-8", capture_output=True, check=True)
        card = decode_card(result.stdout.strip())
        self.assertEqual(card.busy, {7: {14, 15}})
        self.assertEqual(card.semester_start, date(2026, 9, 7))
        self.assertEqual(card.timezone, "UTC+8")
        self.assertEqual(card.period_times, member().period_times)
        self.assertEqual(card.name, "外部成员")


if __name__ == "__main__":
    unittest.main()

"""把'表格'变成课表数据(导入通道的解析核心).

迭代 1 覆盖最常用的一类输入:
- 从教务系统网页 / Excel 复制出来的'格子文字'(粘贴入口);
- .xlsx / .csv 文件(文件入口).

两者共用同一套'网格解析':先认表头(周一...周日),再从每个格子里
拆出'课名 / 教室 / 周次'.格式千奇百怪的情况,留给后面的'导入校对'版本.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from .model import Course, DAYS, parse_day, parse_periods
from .weeks import WEEK_EXPR_RE, looks_like_week_expression

# 拆分"粘连词"时要剥掉的边缘字符(括号,标点等)
_EDGE = "()（）[]【】{}<>《》·,，、;；:：… "


def _is_week_text(t: str) -> bool:
    return looks_like_week_expression(t)


def _looks_like_room(t: str) -> bool:
    """猜一个词是不是教室.宁缺勿错--猜错会把课名弄乱."""
    if not t or len(t) > 12:
        return False
    has_digit = bool(re.search(r"\d", t))
    if has_digit and re.search(r"[楼馆室厅栋区场教]", t):
        return True                       # 信息楼302 / 机房A区101 / 教一A101
    if has_digit and re.search(r"[-\u2014#]", t):
        return True                       # 东4-201 / 11-303
    if re.fullmatch(r"[东南西北中]?[A-Za-z]?\d{3,5}", t):
        return True                       # 西4104 / 4104 / B203
    if re.search(r"(操场|体育馆|游泳馆|礼堂|报告厅|活动中心|会议室)$", t):
        return True                       # 风雨操场 / 校游泳馆
    return False


def _split_plain(text: str) -> list[str]:
    return [t.strip(_EDGE) for t in text.split() if t.strip(_EDGE)]


def _tokenize_cell(cell: str) -> list[str]:
    """把格子文字切成小词, 并把完整周次(含单双周修饰)保留成一个词."""
    text = re.sub(r"[\uff1b;]", " ", str(cell).replace("\r", ""))
    tokens: list[str] = []
    pos = 0
    for m in WEEK_EXPR_RE.finditer(text):
        if not looks_like_week_expression(m.group()):
            continue
        tokens.extend(_split_plain(text[pos:m.start()]))
        week = "".join(m.group().split())
        if week:
            tokens.append(week)
        pos = m.end()
    tokens.extend(_split_plain(text[pos:]))
    return tokens


def _parse_cell(cell: str, notes: Optional[list[str]] = None,
                label: str = "") -> list[tuple[str, str, str]]:
    """解析一个格子 → [(课名, 教室, 周次), ...].

    规则:连续的小词里,出现"周次"之后再冒出新的"非周次非教室"词,
    就认为开始写下一门课了(很多教务系统同一格塞两门课).

    notes / label: 传入时,把"无法识别的内容"记进 notes(导入校对用).
    """
    tokens = _tokenize_cell(cell)
    if not tokens:
        if notes is not None:
            notes.append(f"{label} 里无法识别内容:'{str(cell).strip()[:16]}'")
        return []

    segments: list[list[str]] = [[]]
    for t in tokens:
        seg = segments[-1]
        if seg and not _is_week_text(t) and not _looks_like_room(t) and any(
            _is_week_text(x) for x in seg
        ):
            segments.append([])
        segments[-1].append(t)

    result: list[tuple[str, str, str]] = []
    for seg in segments:
        name_parts: list[str] = []
        room = ""
        weeks = ""
        for t in seg:
            if _is_week_text(t):
                weeks = weeks or t
            elif _looks_like_room(t):
                room = room or t
            else:
                name_parts.append(t)
        if name_parts:
            result.append((" ".join(name_parts).strip(), room, weeks))
        elif notes is not None:
            notes.append(f"{label} 里有一段无法识别:'{' '.join(seg)[:16]}'(已跳过)")
    return result


def parse_grid(rows: list[list], notes: Optional[list[str]] = None) -> list[Course]:
    """rows = 二维表格(第一行一般是表头).无法识别表头时抛 ValueError.

    notes: 传入一个列表时,把"无法识别的格子"这类校对提示追加进去(导入校对用).
    """
    rows = [["" if c is None else str(c).strip() for c in r] for r in rows]

    header_i: Optional[int] = None
    day_cols: dict[int, int] = {}
    for i, r in enumerate(rows[:10]):
        cols: dict[int, int] = {}
        for j, cell in enumerate(r):
            if not cell or len(cell) > 8:      # 表头格一般就"周一"这么短
                continue
            d = parse_day(cell)
            if d is not None and d not in cols:
                cols[d] = j
        if len(cols) >= 3:
            header_i, day_cols = i, cols
            break

    if header_i is None:
        raise ValueError("无法识别课表格子--需要有一行表头写着'周一...周日'")

    first_day_col = min(day_cols.values())
    if first_day_col < 1:
        raise ValueError("表头左边应该还有一列'节次',没找到")
    label_col = first_day_col - 1

    courses: list[Course] = []
    for r in rows[header_i + 1:]:
        if not any(c for c in r):
            continue
        periods = parse_periods(r[label_col] if len(r) > label_col else "")
        if periods is None:
            continue
        start, end = periods
        for day, col in day_cols.items():
            if col >= len(r) or not r[col]:
                continue
            span = f"{start}-{end}" if start != end else str(start)
            label = f"{DAYS[day]} {span} 节"
            for name, room, weeks in _parse_cell(r[col], notes, label):
                courses.append(
                    Course(name=name, day=day, start=start,
                           end=min(end, 12), room=room, weeks=weeks)
                )
    if not courses:
        raise ValueError("表头识别出来了,但格子里没找到课程内容")
    return courses


def _tsv_rows(text: str) -> list[list[str]]:
    """把'表格文字'切成行列.兼容 Excel 复制出来的带引号换行格式."""
    rows: list[list[str]] = []
    row: list[str] = []
    cell: list[str] = []
    in_quote = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if in_quote:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    cell.append('"')
                    i += 2
                    continue
                in_quote = False
                i += 1
                continue
            cell.append(ch)
            i += 1
            continue
        if ch == '"':
            in_quote = True
            i += 1
            continue
        if ch == "\t":
            row.append("".join(cell))
            cell = []
        elif ch == "\n":
            row.append("".join(cell))
            cell = []
            rows.append(row)
            row = []
        elif ch == "\r":
            pass
        else:
            cell.append(ch)
        i += 1
    row.append("".join(cell))
    rows.append(row)
    return rows


def parse_pasted_text(text: str, notes: Optional[list[str]] = None) -> list[Course]:
    """解析剪贴板里的'格子文字'.notes 见 parse_grid."""
    if not text or not text.strip():
        raise ValueError("剪贴板里没有文字.先选中课表,Ctrl+C 复制,再来运行这个命令")

    rows = _tsv_rows(text)
    if all(len(r) <= 1 for r in rows):
        # 没看到制表符:按'连续空格'再切一次;
        # 表头那种 "周一 周二 周三 ..."(单空格)也顺手切开
        new_rows: list[list[str]] = []
        for r in rows:
            line = (r[0] if r else "").strip()
            parts = [p for p in re.split(r"\s{2,}", line) if p] if line else []
            if len(parts) <= 1 and line:
                days = sum(1 for p in line.split() if parse_day(p) is not None)
                if days >= 3:
                    parts = line.split()
            new_rows.append(parts)
        rows = new_rows

    return parse_grid(rows, notes)


def parse_table_file(path, notes: Optional[list[str]] = None, adapter: Optional[dict] = None) -> list[Course]:
    """从 .xlsx / .csv 文件读课表.notes 见 parse_grid."""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"没找到文件:{p}")
    suffix = p.suffix.lower()
    if adapter is not None:
        if suffix in {".xlsx", ".xlsm"}:
            from openpyxl import load_workbook
            wb = load_workbook(p, data_only=True, read_only=True)
            try:
                sheet = wb[adapter["sheet"]] if adapter.get("sheet") else wb.active
                rows = [list(row) for row in sheet.iter_rows(values_only=True)]
                return parse_mapped_rows(rows, adapter, notes)
            finally:
                wb.close()
        if suffix == ".csv":
            with p.open(encoding="utf-8-sig", newline="") as stream:
                return parse_mapped_rows(list(csv.reader(stream)), adapter, notes)
        raise ValueError("格式适配配置仅用于 Excel / CSV.")
    if suffix in {".xlsx", ".xlsm"}:
        return _parse_xlsx(p, notes)
    if suffix == ".csv":
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.reader(f)]
        return parse_grid(rows, notes)
    raise ValueError(f"暂不支持这种文件:{suffix}(现在支持 .xlsx / .csv;"
                     f"Excel 也可以先选中表格'复制→粘贴')")


def parse_mapped_rows(rows: list[list], adapter: dict, notes=None) -> list[Course]:
    """A school adapter maps record columns, without executing Python code."""
    if not isinstance(adapter, dict) or adapter.get("format", "records") != "records":
        raise ValueError("适配配置 format 应为 records.")
    try:
        header_row = int(adapter.get("header_row", 1)) - 1
        mapping = adapter["columns"]
        if header_row < 0 or not isinstance(mapping, dict):
            raise ValueError("invalid mapping")
        headers = [str(value or "").strip() for value in rows[header_row]]
        indexes = {}
        for field in ("name", "day", "periods", "weeks", "room"):
            column = mapping.get(field)
            if column is None and field in {"weeks", "room"}:
                continue
            index = column - 1 if isinstance(column, int) and not isinstance(column, bool) else headers.index(str(column))
            if not 0 <= index < len(headers):
                raise ValueError("invalid column")
            indexes[field] = index
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ValueError("适配配置与文件表头不匹配, 请检查 header_row 和 columns.") from exc
    result = []
    for number, row in enumerate(rows[header_row + 1:], header_row + 2):
        fields = {key: str(row[index] or "").strip() if index < len(row) else "" for key, index in indexes.items()}
        if not any(fields.values()):
            continue
        day = parse_day(fields.get("day", ""))
        span = parse_periods(fields.get("periods", ""))
        if not fields.get("name") or day is None or span is None or not 1 <= span[0] <= span[1] <= 12:
            if notes is not None:
                notes.append(f"第 {number} 行无法确认课程, 星期或节次, 请人工补充.")
            continue
        result.append(Course(fields["name"], day, span[0], span[1], fields.get("room", ""), fields.get("weeks", "")))
    if not result:
        raise ValueError("没有导入有效课程, 请检查格式适配配置.")
    return result


def _parse_xlsx(p: Path, notes: Optional[list[str]] = None) -> list[Course]:
    from openpyxl import load_workbook

    wb = load_workbook(p, data_only=True)
    best: Optional[list[Course]] = None
    best_notes: Optional[list[str]] = None
    for ws in wb.worksheets:
        rows = [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
        try:
            sheet_notes: list[str] = []
            got = parse_grid(rows, sheet_notes)
        except ValueError:
            continue
        if best is None or len(got) > len(best):
            best, best_notes = got, sheet_notes
    if best is None:
        raise ValueError("这个 Excel 里没找到课表格子(需要有一行表头写着'周一...周日')")
    if notes is not None and best_notes:
        notes.extend(best_notes)
    return best


def read_clipboard_text() -> str:
    """读剪贴板里的文字(借 Python 自带的 tkinter,不装额外库)."""
    try:
        import tkinter
    except ImportError:
        return ""
    try:
        root = tkinter.Tk()
        root.withdraw()
        try:
            return str(root.clipboard_get())
        finally:
            root.destroy()
    except Exception:
        return ""

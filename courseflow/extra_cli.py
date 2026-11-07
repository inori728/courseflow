"""Parameter collection and presentation for the new desktop-era commands."""
from __future__ import annotations

from datetime import timedelta
import getpass
from pathlib import Path

from . import service
from .drafts import load_import_draft, load_notice_draft, save_import_draft, save_notice_draft
from .model import DAYS, parse_day, parse_periods
from .settings import AIConfig, AI_REQUIRED


def source(args):
    return service.load_timetable(args.file or "课表.yaml")


def config_ai(args):
    current = service.ai_settings()
    if args.show:
        print("API 地址:", current.base_url or "未配置")
        print("模型:", current.model or "未配置")
        print("API Key:", "已配置" if current.api_key else "未填写")
        print("图片能力:", "已通过自检" if current.vision_verified else "尚未验证")
        return 0
    key = current.api_key
    if args.prompt_key:
        key = getpass.getpass("API Key(不会显示在终端): ")
    config = AIConfig(args.base_url or current.base_url, args.model or current.model, key, args.timeout or current.timeout)
    if config.signature == current.signature:
        config.verified_signature = current.verified_signature
    service.save_ai_settings(config)
    print("配置已保存.", AI_REQUIRED)
    if args.test:
        print(service.test_ai(config))
    return 0


def test_ai(args):
    print(service.test_ai())
    return 0


def vision(args):
    total = source(args).weeks_total if args.file else 16
    draft = service.import_image(args.image, total, args.tiled, print)
    path = save_import_draft(draft, args.out)
    print(f"识别出 {len(draft.courses)} 条课程, 草稿已写入 {path}.")
    for note in draft.notes:
        print("!", note)
    print("原课表未修改. 校对 JSON 中的课程后, 使用 term accept 草稿 --confirm 保存.")
    return 0


def accept(args):
    target = Path(args.out)
    total = service.load_timetable(target).weeks_total if target.exists() else 16
    draft = load_import_draft(args.draft, total)
    tt = service.prepare_import(draft.courses, target)
    service.save_timetable(tt, target)
    print(f"已确认并保存 {len(tt)} 条课程到 {target}, 原文件已按需备份.")
    for note in draft.notes:
        print("!", note)
    return 0


def notice(args):
    tt = source(args)
    text = Path(args.text_file).read_text(encoding="utf-8") if args.text_file else args.text
    if not text:
        raise ValueError("请提供通知文字或 --text-file.")
    intent = service.interpret_notification(tt, text)
    path = save_notice_draft(intent, tt, args.out)
    print("通知草稿已生成:", path)
    try:
        candidates = service.notice_candidates(tt, intent)
        for index, candidate in enumerate(candidates, 1):
            print(f"{index}. {candidate.describe()}")
        if not candidates:
            print("没有匹配课次, 请核对草稿中的课程名称和原周次.")
    except ValueError as exc:
        print("待补充:", exc)
    print("未修改课表. 使用 term notice-preview 草稿 --select 序号 预览, --apply --confirm 才保存.")
    return 0


def notice_preview(args):
    tt = source(args)
    intent, selection, overrides = load_notice_draft(args.draft, tt)
    if args.target_week is not None:
        intent.target_week = args.target_week
    if args.target_day is not None:
        intent.target_day = parse_day(args.target_day)
        if intent.target_day is None:
            raise ValueError("目标星期无法识别.")
    if args.target_periods:
        intent.target_periods = args.target_periods
    candidates = service.notice_candidates(tt, intent)
    for index, candidate in enumerate(candidates, 1):
        print(f"{index}. {candidate.describe()}")
    if args.select:
        try:
            selection = [int(number.strip()) for number in args.select.split(",")]
        except ValueError as exc:
            raise ValueError("--select 示例: 1 或 1,2.") from exc
    if not selection:
        print("请通过 --select 选择课次, 或在草稿 selection 中填写序号列表.")
        return 0
    if any(isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= len(candidates) for index in selection):
        raise ValueError("所选课次序号超出范围.")
    # Per-candidate day values in JSON use Chinese names, just like intent fields.
    normalized = {}
    for token, fields in overrides.items():
        if not isinstance(fields, dict):
            raise ValueError("每条 overrides 应为对象.")
        fields = dict(fields)
        if "target_day" in fields:
            fields["target_day"] = parse_day(fields["target_day"])
        normalized[token] = fields
    preview = service.notice_preview(tt, intent, [candidates[index - 1] for index in selection], normalized)
    for before, after in preview.rows:
        print("原:", before)
        print("新:", after)
    for conflict in preview.new_conflicts:
        print("冲突:", conflict)
    if args.apply:
        if not args.confirm:
            raise ValueError("实际保存还需同时提供 --confirm, 请先检查预览.")
        changed = service.apply_notification(tt, preview)
        service.save_timetable(changed, args.file or "课表.yaml")
        print("已确认并保存调整.")
    else:
        print("预览完成, 尚未保存.")
    return 1 if preview.new_conflicts else 0


def busycard(args):
    tt = source(args)
    weeks = [args.week] if args.week is not None else None
    card = service.make_busy_card(tt, args.name, weeks, args.campus)
    path = service.export_busy_card(card, args.out)
    print("忙闲卡已导出:", path)
    print("卡片只含成员名称, 学期/作息和忙闲信息, 不含课程名称与教室.")
    return 0


def read_members(paths):
    members = []
    for path in paths:
        target = Path(path)
        if target.suffix.lower() in {".yaml", ".yml"}:
            members.append(service.make_busy_card(service.load_timetable(target), target.stem))
        else:
            members.append(service.read_busy_card(target.read_text(encoding="utf-8")))
    return members


def group(args):
    result = service.group_free(read_members(args.members), args.week, args.min_periods)
    print(result.describe())
    if args.out:
        folder = Path(args.out)
        folder.mkdir(parents=True, exist_ok=True)
        from .settings import atomic_text
        atomic_text(folder / "全员空闲.txt", result.describe() + "\n")
        service.export_group_heatmap(result, folder / "忙闲热力图.png")
        print("结果已导出到:", folder)
    return 0


def meeting(args):
    result = service.group_free(read_members(args.members), args.week, 1)
    day, periods = parse_day(args.day), parse_periods(args.periods)
    if day is None or periods is None:
        raise ValueError("请填写有效星期和节次.")
    window = next((w for w in result.windows if w.day == day and w.start <= periods[0] <= periods[1] <= w.end), None)
    if window is None:
        raise ValueError("所选时间不在全员空闲范围内.")
    service.export_group_meeting(result, window, args.title, args.out, *periods)
    print("会议日历已导出:", args.out)
    return 0


def poster(args):
    print(service.export_poster(source(args), args.out, args.week))
    return 0


def share(args):
    print(service.export_share_card(source(args), args.out, args.week))
    return 0


def agenda(args):
    from .agenda import local_today
    tt = source(args)
    day = local_today(tt) + timedelta(days=1 if args.tomorrow else 0)
    if getattr(args, "week_view", False):
        if tt.semester_start is None:
            raise ValueError("请先填写学期起始日期.")
        week = args.week or service.current_week(tt)
        if not 1 <= week <= tt.weeks_total:
            raise ValueError("周次超出学期范围.")
        monday = tt.semester_start + timedelta(weeks=week - 1)
        for delta in range(7):
            print(service.agenda(tt, monday + timedelta(days=delta)))
    else:
        print(service.agenda(tt, day))
    return 0


def gui(args):
    from .gui import main
    main(args.file)
    return 0


def point_grid(args):
    target = service.export_point_grid(args.out)
    print("零安装点格页已复制到:", target)
    return 0


def register(sub):
    def parser(name, help_text, handler, aliases=()):
        result = sub.add_parser(name, aliases=list(aliases), help=help_text)
        result.set_defaults(handler=handler)
        return result
    def file_flag(result):
        result.add_argument("-f", "--file", help="课表源文件(默认 课表.yaml)")
    p = parser("config-ai", "配置共用多模态 AI 接口", config_ai)
    p.add_argument("--base-url")
    p.add_argument("--model")
    p.add_argument("--timeout", type=int)
    p.add_argument("--prompt-key", action="store_true", help="交互输入 Key, 不写入命令历史")
    p.add_argument("--test", action="store_true")
    p.add_argument("--show", action="store_true")
    parser("test-ai", "验证共用 AI 的图片识别能力", test_ai)
    p = parser("vision", "识图生成待校对草稿, 不覆盖课表", vision)
    p.add_argument("image")
    p.add_argument("--tiled", action="store_true")
    file_flag(p)
    p.add_argument("-o", "--out", default="识图结果.ai-draft.json")
    p = parser("accept", "确认已校对的识图草稿", accept)
    p.add_argument("draft")
    p.add_argument("--confirm", action="store_true", required=True)
    p.add_argument("-o", "--out", default="课表.yaml")
    p = parser("gui", "打开三步图形界面", gui)
    file_flag(p)

window.__ModuleLoader__.load({
  id: 'dsh-courseflow',
  factory(require) {
    const { createElement: h, useEffect, useRef, useState, useSyncExternalStore } = require('react')
    const plugin = 'dsh-courseflow'
    const tabKind = 'courseflow'
    const sections = { agenda: '课表', import: '导入', adjust: '调课', group: '组队', schedule: '日程', todos: '待办', export: '导出' }
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    const formats = { desktop: '电脑壁纸', phone: '手机壁纸', yaml: '课表 YAML', ics: '日历 ICS', pdf: 'A4 PDF', png: '挂图 PNG' }
    const wallpaperPresets = { dusk: '樱花电车', night: '月夜海岸', sea: '海边教室', purple: '山间静湖' }
    const scheduleStyles = { green: '墨绿日程', simple: '简洁清单' }
    const maxAttachmentBytes = 12 * 1024 * 1024
    const css = `
      .cf-ui{--cf-bg:var(--dsw-alias-bg-base,#fff);--cf-ink:var(--dsw-alias-label-primary,#17233d);--cf-line:var(--dsw-alias-border-l3,#dce3ef);--cf-accent:#4055db;box-sizing:border-box;color:var(--cf-ink);font:14px/1.5 "Microsoft YaHei UI",Inter,sans-serif;pointer-events:auto}
      .cf-ui *{box-sizing:border-box}.cf-ui h2,.cf-ui h3,.cf-ui p{margin:0}.cf-ui h2{font-size:18px}.cf-ui h3{font-size:15px}
      .cf-ui button,.cf-ui input,.cf-ui select,.cf-ui textarea{font:inherit}.cf-ui button{border:1px solid var(--cf-line);border-radius:8px;background:var(--cf-bg);color:inherit;padding:6px 10px;cursor:pointer}.cf-ui button:hover:not(:disabled){border-color:var(--cf-accent)}.cf-ui button:disabled{cursor:default;opacity:.55}.cf-ui .cf-primary{background:var(--cf-accent);color:#fff;border-color:var(--cf-accent)}
      .cf-ui input:not([type="checkbox"]),.cf-ui select,.cf-ui textarea{min-width:0;width:100%;padding:6px 8px;border:1px solid var(--cf-line);border-radius:7px;background:var(--cf-bg);color:inherit}.cf-ui input[type=checkbox]{accent-color:var(--cf-accent);margin:0 6px 0 0;vertical-align:middle}.cf-ui textarea{resize:vertical}
      .cf-pane{height:100%;min-height:0;display:flex;flex-direction:column;container-type:inline-size;background:var(--cf-bg)}
      .cf-pane-header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:6px;padding:8px 12px;border-bottom:1px solid var(--cf-line)}
      .cf-nav{display:flex;flex-wrap:wrap;gap:3px}.cf-ui .cf-nav button,.cf-ui .cf-icon{border-color:transparent;background:transparent;padding:5px 8px}.cf-ui .cf-nav [aria-current=page]{background:#e9edff;color:#283d92;font-weight:600}.cf-ui .cf-icon{display:grid;place-items:center;padding:5px}
      .cf-composer{display:grid;place-items:center;flex:none;width:30px;height:30px;border:0;border-radius:7px;background:transparent;color:var(--dsw-alias-label-secondary,#56627a);cursor:pointer}.cf-composer:hover,.cf-composer[aria-pressed=true]{background:#e9edff;color:#283d92}.cf-composer:disabled{opacity:.55;cursor:default}
      .cf-pane-body{flex:1;min-height:0;overflow:auto;scrollbar-gutter:stable;padding:14px;align-content:start;overflow-wrap:anywhere}.cf-pane-body fieldset{margin:0;padding:10px;border:1px solid var(--cf-line);border-radius:9px;min-width:0}
      .cf-pane > [hidden]{display:none}
      .cf-background-preview{margin:0;overflow:hidden;border:1px solid var(--cf-line);border-radius:9px}.cf-background-preview img{display:block;width:100%;height:auto;max-height:300px;object-fit:contain}.cf-background-preview>p{padding:10px 12px}
      .cf-wallpaper-previews{display:flex;flex-wrap:wrap;align-items:flex-start;gap:8px}.cf-wallpaper-previews figure{flex:1 1 230px;min-width:0;margin:0;padding:8px;border:1px solid var(--cf-line);border-radius:9px}.cf-wallpaper-previews img{display:block;max-width:100%;max-height:540px;width:auto;height:auto;margin:0 auto 6px}
      .cf-toast{position:absolute;top:52px;right:20px;width:308px;max-width:calc(100vw - 40px);background:var(--cf-bg);border:1px solid var(--cf-line);border-radius:12px;box-shadow:0 5px 24px #1925541a;padding:14px}
      .cf-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.cf-between{justify-content:space-between}.cf-v{display:grid;gap:10px;min-width:0}.cf-muted{opacity:.75}.cf-note,.cf-error,.cf-ok{border-radius:8px;padding:8px 10px}.cf-note{background:#e9edff;color:#283d92}.cf-error{background:#fff0f0;color:#9b232d}.cf-ok{background:#e5f7eb;color:#20583b}.cf-ui summary{cursor:pointer}.cf-ui details[open]>summary{margin-bottom:8px}
      .cf-next{border:1px solid var(--cf-line);border-left:3px solid var(--cf-accent);border-radius:9px;padding:10px 12px;display:grid;gap:3px}.cf-day-list{list-style:none;margin:0;padding:0}.cf-day-list li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding:6px 0;border-bottom:1px solid var(--cf-line)}.cf-ui .cf-week input{width:68px}
      .cf-grid2,.cf-grid3,.cf-grid4{display:grid;gap:8px}.cf-grid2{grid-template-columns:repeat(2,minmax(0,1fr))}.cf-grid3{grid-template-columns:repeat(3,minmax(0,1fr))}.cf-grid4{grid-template-columns:repeat(4,minmax(0,1fr))}
      .cf-field{display:grid;gap:4px}.cf-table{border-collapse:collapse;width:100%;min-width:440px}.cf-table td,.cf-table th{border-bottom:1px solid var(--cf-line);padding:5px 3px;text-align:left}.cf-table td:first-child{min-width:112px}.cf-scroll{overflow:auto;max-height:420px}.cf-grid-heat{display:grid;grid-template-columns:minmax(76px,1fr) repeat(7,minmax(43px,1fr));gap:4px;align-items:center;min-width:405px;text-align:center}
      .cf-grid-heat .cf-free{background:#daf3e6;color:#1d5339;border:1px solid transparent;padding:5px 2px}.cf-grid-heat .cf-busy{background:#e4eafe;color:#2c487c;border-radius:7px;padding:5px 2px}.cf-grid-heat small{display:block}.cf-compare{display:grid;grid-template-columns:1fr 1fr;gap:8px}.cf-compare>div{border:1px solid var(--cf-line);padding:8px;border-radius:8px}.cf-listline{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font:inherit}
      .cf-day{border:1px solid var(--cf-line);border-radius:12px;padding:10px 12px;display:grid;grid-template-columns:57px minmax(0,1fr);gap:10px}
      .cf-today{background:#eaf1ff;color:#213e70}.cf-day h3 small,.cf-week-grid small{display:block;font-weight:400}.cf-day .cf-day-list li:last-child{border-bottom:0}
      .cf-course-period{padding:1px 5px;border-radius:5px;background:#e9edf8;color:#34436b;white-space:nowrap}.cf-course-room{margin-left:auto}.cf-day .cf-day-list strong{font-size:13px}
      .cf-week-grid{display:grid;width:100%;min-width:320px;grid-template-columns:33px repeat(7,minmax(0,1fr));color:#233654;background:#fff;border:1px solid #d8e2ee;border-radius:10px;overflow:hidden}
      .cf-week-column{display:grid;grid-template-rows:42px repeat(12,48px);border-right:1px solid #d8e2ee;min-width:0}
      .cf-week-heading{text-align:center;line-height:1.25;padding:6px 2px;grid-row:1;z-index:1}.cf-week-period{border-top:1px solid #dce5ef;text-align:center;padding:6px 2px;font-size:12px;grid-column:1/-1}
      .cf-week-lesson{display:flex;flex-direction:column;gap:2px;overflow:hidden;line-height:1.25;align-self:stretch;margin:2px;border-radius:5px;padding:3px 4px;font-size:11px;z-index:1;border-left:3px solid #6377c2;background:#e6ebfa;color:#263862}
      .cf-week-lesson:nth-of-type(3n){background:#e3f3ed;border-color:#3f8a72;color:#245b4a}.cf-week-lesson:nth-of-type(3n+1){background:#f3ebf9;border-color:#9370ae;color:#573e6a}
      .cf-week-lesson span,.cf-week-lesson strong{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;overflow-wrap:anywhere}
      .cf-plan-row{display:grid;grid-template-columns:minmax(55px,1fr) minmax(110px,2fr) auto;gap:6px;align-items:center}.cf-plan-preview{display:block;max-width:100%;height:auto;border:1px solid var(--cf-line);border-radius:8px}
      .cf-task{padding:8px 0;border-bottom:1px solid var(--cf-line)}.cf-task label{overflow-wrap:anywhere}.cf-task-complete label{opacity:.7;text-decoration:line-through}.cf-option{border:1px solid var(--cf-line);border-radius:10px;padding:9px}.cf-option.cf-preferred{border-color:#6f9c86;background:#edf8f1;color:#27563d}
      @container (max-width:520px){.cf-grid4{grid-template-columns:repeat(2,minmax(0,1fr))}}
      @container (max-width:350px){.cf-pane-body{padding:10px}.cf-grid3,.cf-compare{grid-template-columns:1fr}}
    `

    const button = (label, onClick, primary = false, disabled = false) => h('button', {
      type: 'button', className: primary ? 'cf-primary' : undefined, onClick, disabled,
    }, label)
    const field = (label, value, onChange, props = {}) => h('label', { className: 'cf-field' },
      h('span', null, label), h('input', { value: value ?? '', onChange: (e) => onChange(e.target.value), ...props }))
    const check = (label, value, onChange) => h('label', null,
      h('input', { type: 'checkbox', checked: value, onChange: (e) => onChange(e.target.checked) }), label)
    const note = (value, cssName = 'cf-note') => value ? h('p', { className: cssName }, value) : null
    const entry = (row) => row && [row.date, row.clock || `${row.start}-${row.end} 节`, row.kind === 'activity' ? `[组队] ${row.name}` : row.name, row.room].filter(Boolean).join(' · ')
    const errorText = (error) => error?.message || String(error)

    function CalendarIcon() {
      return h('svg', { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
        strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
      h('rect', { x: 3.5, y: 5.5, width: 17, height: 15.5, rx: 2.5 }),
      h('path', { d: 'M7.5 3.5v4m9-4v4m-13 2.5h17M8 14h2m4 0h2m-8 3.5h2' }))
    }

    function GearIcon() {
      return h('svg', { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
        strokeWidth: 1.7, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true },
      h('path', { d: 'M3 7h8m4 0h6M3 17h3m4 0h11' }),
      h('circle', { cx: 13, cy: 7, r: 2 }), h('circle', { cx: 8, cy: 17, r: 2 }))
    }

    async function call(ctx, action, payload = {}, session = '') {
      const result = await ctx.connection.rpc.call('/api', 'courseflow/operate', { args: {
        request: { action, payload, session },
      } }, AbortSignal.timeout(250_000))
      if (!result.ok) return { ok: false, error: result.error.message }
      return result.value
    }

    async function download(ctx, id) {
      const response = await call(ctx, 'download', { id })
      if (!response.ok) throw new Error(response.error)
      const data = Uint8Array.from(atob(response.value.base64), value => value.charCodeAt(0))
      const url = URL.createObjectURL(new Blob([data]))
      const link = document.createElement('a')
      link.href = url
      link.download = response.value.name
      document.body.append(link)
      link.click()
      link.remove()
      setTimeout(() => URL.revokeObjectURL(url), 30_000)
    }

    function FileList({ files = [], ctx, onError }) {
      if (!files.length) return null
      return h('div', { className: 'cf-row' }, files.map(file => h('button', {
        key: file.id, type: 'button', onClick: () => download(ctx, file.id).catch(error => onError(errorText(error))),
      }, `保存 ${file.name}`)))
    }

    function Settings({ ctx, onSaved, onResume, open }) {
      const [settings, setSettings] = useState(null)
      const [key, setKey] = useState('')
      const [problem, setProblem] = useState('')
      const [saved, setSaved] = useState('')
      const [busy, setBusy] = useState(false)
      const [clear, setClear] = useState(false)
      useEffect(() => {
        let mounted = true
        call(ctx, 'settings').then(response => {
          if (!mounted) return
          if (response.ok) setSettings(response.value)
          else setProblem(response.error)
        }).catch(error => mounted && setProblem(errorText(error)))
        return () => { mounted = false }
      }, [ctx])
      if (!settings) return note(problem || '正在读取设置...', problem ? 'cf-error' : 'cf-note')
      const update = (field, value) => setSettings({ ...settings, [field]: value })
      async function save(event) {
        event.preventDefault()
        setBusy(true)
        setProblem('')
        setSaved('')
        try {
          const response = await call(ctx, 'save_settings', {
            base_url: settings.base_url, model: settings.model, timeout: Number(settings.timeout), api_key: key, clear_key: clear,
          })
          setKey('')
          if (!response.ok) {
            setProblem(response.error)
            const current = await call(ctx, 'settings')
            if (current.ok) setSettings(current.value)
            return
          }
          setClear(false)
          setSettings(response.value)
          setSaved(response.value.message)
          onSaved?.()
        } catch (error) {
          setProblem(errorText(error))
        } finally {
          setBusy(false)
        }
      }
      return h('form', { className: 'cf-ui cf-v', onSubmit: save, autoComplete: 'off' },
        h('h3', null, 'CourseFlow AI 接口设置'),
        h('p', { className: 'cf-muted' }, '请配置具备多模态能力（支持文字和图片识别）的接口。桌面端和插件共用此设置。'),
        field('接口地址', settings.base_url, value => update('base_url', value), { required: true, placeholder: 'https://api.example.com/v1' }),
        field('模型名', settings.model, value => update('model', value), { required: true }),
        field('API Key', key, setKey, { type: 'password', autoComplete: 'new-password',
          placeholder: settings.has_key ? '已配置，留空保留' : '填写提供方要求的 Key' }),
        settings.has_key && check('清除已保存的 Key', clear, setClear),
        field('超时秒数', settings.timeout, value => update('timeout', value), { type: 'number', min: 5, max: 300, required: true }),
        note(problem, 'cf-error'), note(saved || (settings.verified ? '多模态自检已通过' : '多模态自检尚未通过'), settings.verified ? 'cf-ok' : 'cf-note'),
        h('div', { className: 'cf-row' },
          h('button', { type: 'submit', className: 'cf-primary', disabled: busy }, busy ? '正在自检...' : '保存并自检'),
          onResume && button('继续刚才的操作', onResume, false, busy || !settings.verified),
          open && button('打开 CourseFlow 工作台', open)),
      )
    }

    function TableEditor({ table, setTable }) {
      const change = (index, name, value) => setTable({ ...table, courses: table.courses.map((row, i) => i === index ? {...row, [name]: value } : row) })
      const semester = table.semester
      const setSemester = (key, value) => setTable({ ...table, semester: { ...semester, [key]: value }, semesterEdited: true })
      const dates = !semester.start
      const cellField = (key, row, i, type) => {
        if (table.editable && type === 'day') {
          return h('select', { value: row.day, 'aria-label': '星期', onChange: (event) => change(i, key, event.target.value) },
            days.map(day => h('option', { key: day }, day)))
        }
        return table.editable ? h('input', { value: row[key], 'aria-label': key, onChange: event => change(i, key, event.target.value) }) : row[key]
      }
      return h('div', { className: 'cf-v' },
        table.warnings?.length ? note(table.warnings.join(' / ')) : null,
        h('details', { open: dates || undefined }, h('summary', null, '学期与作息', semester.start && ` · ${semester.start}`),
          h('div', { className: 'cf-grid4' },
            field('学期名称', semester.term, value => setSemester('term', value)),
            field('第 1 周周一', semester.start, value => setSemester('start', value), { type: 'date' }),
            field('学期周数', semester.total, value => setSemester('total', value), { type: 'number', min: 1, max: 104 }),
            field('时区', semester.timezone, value => setSemester('timezone', value))),
          h('div', { className: 'cf-grid4' }, Array.from({ length: 12 }, (_, i) => field(
            `第 ${i + 1} 小节`, semester.clocks[i + 1],
            value => setSemester('clocks', { ...semester.clocks, [i + 1]: value }), { key: i, placeholder: '08:00-08:45' }))),
          button('套用 08:00–22:40 作息', () => setSemester('clocks', table.school_clocks))),
        h('details', { open: table.editable || undefined }, h('summary', null, `校对 ${table.courses.length} 条课程`),
          h('div', { className: 'cf-scroll' }, h('table', { className: 'cf-table' },
            h('thead', null, h('tr', null, ['课程', '星期', '节次', '周次', '地点', ''].map(label => h('th', { key: label }, label)))),
            h('tbody', null, table.courses.map((row, i) => h('tr', { key: i },
              ['name', 'day', 'periods', 'weeks', 'room'].map(key => h('td', { key }, cellField(key, row, i, key))),
              h('td', null, table.editable && (!row.kind || row.kind !== 'activity') &&
                button('移除', () => setTable({ ...table, courses: table.courses.filter((_, index) => index !== i) })))))))),
          table.editable && button('补一条课程', () => setTable({ ...table, courses: [
            ...table.courses, { name: '', day: days[0], periods: '', weeks: '', room: '' },
          ] }))),
      )
    }

    function tableEdits(table) {
      return {
        ...(table.semesterEdited || table.editable && table.semester.start ? { semester: table.semester } : {}),
        ...(table.editable ? { courses: table.courses } : {}),
      }
    }

    function Preparation({ data, submit, busy }) {
      const [table, setTable] = useState(data.table)
      const send = () => submit(tableEdits(table))
      return h('div', { className: 'cf-v' },
        note(data.overwrite && (data.change || data.imported) ? `确认后将更新共用的 ${data.source}。` : ''),
        data.formats.length > 0 && h('p', { className: 'cf-muted' }, data.formats.map(value => formats[value]).join('、')),
        data.wallpaper_background && h('p', { className: 'cf-muted' }, `壁纸背景 · ${data.wallpaper_background}`),
        h(TableEditor, { table, setTable }),
        h('div', { className: 'cf-row' }, button(data.change ? '查找课次并预览' : data.imported && data.overwrite ? '预览导入' : '预览导出', send, true, busy)),
      )
    }

    function Preview({ data, select, apply, back, busy }) {
      const [selected, setSelected] = useState(data.selected || [])
      const [chosen, setChosen] = useState(false)
      return h('div', { className: 'cf-v' },
        data.candidates?.length > 1 && h('fieldset', { className: 'cf-v' },
          h('legend', null, `找到 ${data.candidates.length} 个候选课次`),
          ...data.candidates.map(item => h('div', { key: item.id }, check(`${item.label} ${item.clock}`, selected.includes(item.id),
            value => { setChosen(true); setSelected(value ? [...selected, item.id] : selected.filter(id => id !== item.id)) }))),
          button('查看所选课次的预览', () => { setChosen(false); select(selected) }, false, busy || !selected.length)),
        data.rows.map((row, i) => h('div', { key: i, className: 'cf-compare' },
          h('div', null, h('h3', null, '原安排'), row.before), h('div', null, h('h3', null, '新安排'), row.after))),
        data.conflicts?.length > 0 && note(data.conflicts.join(' / '), 'cf-error'),
        data.confirmation && data.change && note('已检查时间冲突，等待你确认。', 'cf-ok'),
        note(data.warnings?.length ? data.warnings.join(' / ') : ''),
        note(data.overwrite ? `确认后写回 ${data.source}，桌面端会刷新。` : ''),
        data.formats.length > 0 && h('p', { className: 'cf-muted' }, `生成 ${data.formats.map(value => formats[value]).join('、')}`),
        data.wallpaper_background && h('p', { className: 'cf-muted' }, `壁纸背景 · ${data.wallpaper_background}`),
        data.wallpaper_previews && Object.keys(data.wallpaper_previews).length > 0 && h('div', { className: 'cf-wallpaper-previews' },
          Object.entries(data.wallpaper_previews).map(([format, image]) => h('figure', { key: format },
            h('img', { src: `data:image/jpeg;base64,${image}`, alt: `${formats[format]}预览`, decoding: 'async' }),
            h('figcaption', null, formats[format])))),
        h('div', { className: 'cf-row' }, button('返回核对', back, false, busy),
          data.confirmation && button(data.overwrite ? data.change ? '确认调课' : '确认导入' : '确认生成',
            () => apply(data.confirmation), true, busy || chosen)),
      )
    }

    function GroupReview({ data, timetable, submit, busy }) {
      const [members, setMembers] = useState(data.members)
      const [week, setWeek] = useState(data.week)
      const [minimum, setMinimum] = useState(data.minutes || data.minimum)
      const [minutes, setMinutes] = useState(Boolean(data.minutes))
      const [own, setOwn] = useState(data.include_self)
      const update = (i, value) => setMembers(members.map((member, index) => index === i ? value : member))
      const first = members[0]
      const reference = first ? first.semester?.start ?? first.start : timetable?.semester_start
      const maxWeek = Number(first ? first.semester?.total : timetable?.weeks_total) || 104
      const requestedWeek = Number(week)
      const validWeek = Number.isInteger(requestedWeek) && requestedWeek >= 1 && requestedWeek <= maxWeek
      const dayMs = 86_400_000
      const weekMs = 7 * dayMs
      const monday = validWeek ? Date.parse(`${reference}T00:00:00Z`) + (requestedWeek - 1) * weekMs : NaN
      const hasDate = Number.isFinite(monday)
      const missingCards = hasDate ? members.filter(member => member.weeks &&
        !member.weeks.includes(1 + (monday - Date.parse(`${member.start}T00:00:00Z`)) / weekMs)) : []
      return h('div', { className: 'cf-v' },
        h('p', { className: 'cf-muted' }, first ? '查询周次以第一位成员的学期日期为准。' : '查询周次以我的课表的学期日期为准。'),
        note(data.warning),
        ...members.map((member, i) => h('fieldset', { key: i, className: 'cf-v' },
          field('成员名称', member.name, name => update(i, { ...member, name }), { maxLength: 80 }),
          member.courses ? h(TableEditor, { table: member, setTable: value => update(i, value) }) :
            h('p', { className: 'cf-muted' }, `第 1 周周一 ${member.start} · 已提供第 ${member.weeks.join('、')} 周`))),
        data.can_include_self && check('加入我已保存的课表', own, setOwn),
        own && timetable?.weeks_total && h('p', { className: 'cf-muted' },
          `我的课表学期共 ${timetable.weeks_total} 周。可在桌面版「我的课表 → 学期与作息」修改学期总周数。`),
        h('div', { className: 'cf-grid3' },
          field('查询周次', week, setWeek, { type: 'number', min: 1, max: maxWeek }),
          field(minutes ? '最少分钟数' : '最少连续小节', minimum, setMinimum, { type: 'number', min: 1, max: minutes ? 1440 : 12 }),
          check('按分钟筛选', minutes, setMinutes)),
        hasDate && h('p', { className: 'cf-muted' },
          `本次查询 ${new Date(monday).toISOString().slice(0, 10)} 至 ${new Date(monday + 6 * dayMs).toISOString().slice(0, 10)}。`),
        week !== '' && !validWeek && note(`查询周次应为 1 至 ${maxWeek} 之间的整数。`),
        missingCards.length > 0 && note(`${missingCards.map(member => member.name).join('、')} 的忙闲卡未覆盖这段日期。请选择有资料的一周，或补充所查日期的忙闲卡。`),
        h('p', { className: 'cf-muted' }, '按分钟筛选需要完整的 12 节作息，午休等长间隔会分开。缺钟点时可先按小节查找。'),
        button('查找共同空闲', () => submit({ token: data.token, members: members.map(member => ({
          name: member.name, ...(member.courses ? tableEdits(member) : {}),
        })), week: requestedWeek, minimum: minutes ? 1 : Number(minimum), minutes: minutes ? Number(minimum) : 0, include_self: own }),
        true, busy || !validWeek || !minimum || missingCards.length > 0),
      )
    }

    function Heatmap({ data, select, exportGrid, preferPair, setPreferPair, target, setTarget, task, busy }) {
      const labelSlot = (day, first, last) => {
        const start = data.clocks[first]?.split('-')[0]
        const end = data.clocks[last]?.split('-')[1]
        return `${data.dates[day]} ${days[day]} · ${first === last ? first : `${first}-${last}`} 节${start && end ? ` · ${start}–${end}` : ''}`
      }
      return h('div', { className: 'cf-v' },
        h('p', { className: 'cf-muted' }, `第 ${data.week} 周 · ${data.names.join('、')}`),
        note(data.warnings?.join(' / ')),
        data.clock_source === 'default' && note('缺失的钟点已带入兼容的默认作息。'),
        h('div', { className: 'cf-row' }, button('导出点格页', exportGrid, false, busy),
          check('优先选同组两节', preferPair, setPreferPair)),
        !task && h('label', { className: 'cf-field' }, '点选空档后',
          h('select', { 'aria-label': '点选空档后', value: target, onChange: event => setTarget(event.target.value), disabled: busy },
            h('option', { value: 'schedule' }, '打开小组日程'),
            h('option', { value: 'personal' }, '添加个人课表活动'),
            h('option', { value: 'clocks' }, '先修改本次作息'))),
        h('p', { className: 'cf-muted' }, '默认按 1–2、3–4 等成对选择。另一节有人忙时，只选点中的空闲格。'),
        h('details', { open: !data.windows.length || undefined },
          h('summary', null, `符合条件的连续空闲时段（${data.windows.length}）`),
          h('div', { className: 'cf-v' }, ...data.windows.map((item, i) => h('div', { className: 'cf-row', key: i },
            button(labelSlot(item.day, item.start, item.end), () => select(item), false, busy))))),
        h('div', { className: 'cf-scroll' }, h('div', { className: 'cf-grid-heat' },
          h('span', null, '小节'),
          ...days.map((day, i) => h('strong', { key: day }, day, h('small', null, data.dates[i].slice(5)))),
          ...Array.from({ length: 12 }, (_, i) => [
            h('span', { key: `p${i}` }, i + 1, h('small', null, data.clocks[i + 1] || '')),
            ...days.map((day, j) => {
              const count = data.counts[j * 12 + i]
              return count
                ? h('span', { key: day + i, className: 'cf-busy' }, `${count} 人忙`)
                : h('button', {
                  type: 'button', key: day + i, className: 'cf-free',
                  title: labelSlot(j, i + 1, i + 1), disabled: busy,
                  onClick: () => select({ day: j, start: i + 1, end: i + 1, prefer_pair: preferPair }),
                }, '空闲')
            }),
          ]).flat(),
        )),
      )
    }

    function ActivityClocks({ slot, back, submit, busy }) {
      const [clocks, setClocks] = useState(slot.clocks)
      const { start, end } = slot.fields
      const periods = Array.from({ length: end - start + 1 }, (_, i) => start + i)
      const fill = values => setClocks({ ...clocks, ...values, ...slot.known_clocks })
      return h('form', { className: 'cf-v', onSubmit(event) {
        event.preventDefault()
        submit(clocks)
      } },
      note(slot.label),
      h('p', null, slot.needs_clocks ? '请补齐所选节次的钟点。' : '可以调整默认带入的钟点。'),
      h('div', { className: 'cf-row' },
        slot.clock_choices.personal && button('填入我的课表作息', () => fill(slot.clock_choices.personal), false, busy),
        slot.clock_choices.preset && button('填入 08:00–22:40 预设', () => fill(slot.clock_choices.preset), false, busy)),
      h('div', { className: 'cf-grid4' }, periods.map(period => field(`第 ${period} 小节`, clocks[period],
        value => setClocks({ ...clocks, [period]: value }), {
          key: period, placeholder: 'HH:MM-HH:MM', maxLength: 11, disabled: busy, readOnly: Boolean(slot.known_clocks?.[period]),
          required: period === start || period === end,
        }))),
      h('p', { className: 'cf-muted' }, '确认的钟点只用于本次组队。'),
      h('div', { className: 'cf-row' }, button(slot.needs_clocks ? '返回忙闲图' : '取消修改', back, false, busy),
        h('button', { type: 'submit', className: 'cf-primary', disabled: busy }, '确认本次作息')))
    }

    function Activity({ slot, back, submit, plan, setGroupClocks, busy, present }) {
      const [title, setTitle] = useState(slot.task?.title || '')
      const [place, setPlace] = useState('')
      const [exportIcs, setExportIcs] = useState(false)
      const [editingClocks, setEditingClocks] = useState(false)
      if (editingClocks || slot.needs_clocks) {
        return h(ActivityClocks, { key: slot.token, slot, busy,
          back: slot.needs_clocks ? back : () => setEditingClocks(false),
          submit: async clocks => { if (await setGroupClocks(clocks)) setEditingClocks(false) },
        })
      }
      return h('form', { className: 'cf-v', onSubmit(event) {
        event.preventDefault()
        if (title.trim()) submit({ ...slot.fields, title, room: place, export_ics: exportIcs })
      } },
      note(slot.label),
      slot.pair_note && h('p', { className: 'cf-muted' }, slot.pair_note),
      h('p', { className: 'cf-muted' }, '保存会把这段空档留在你的个人课表。制定小组日程会打开议程和分工编辑。'),
      slot.can_edit_clocks && h('div', { className: 'cf-row' },
        slot.clock_source === 'default' && h('span', { className: 'cf-muted' }, '当前使用默认作息'),
        button('修改本次作息', () => setEditingClocks(true), false, busy)),
      field('活动名称', title, setTitle, { autoFocus: true, required: true, maxLength: 120 }),
      field('地点（选填）', place, setPlace, { maxLength: 120 }),
      present ? check('同时导出会议 ICS', exportIcs, setExportIcs) : note('导入我的课表后，可以把这段时间存为活动。'),
      h('div', { className: 'cf-row' }, button('返回忙闲图', back, false, busy),
        button('制定小组日程', plan, false, busy),
        h('button', { type: 'submit', className: 'cf-primary', disabled: busy || !present || !title.trim() }, '保存到我的课表')))
    }

    const panelTitles = {
      prepare: '校对课表', preview: '操作预览', agenda: '课程查询', group_prepare: '核对组队资料',
      group_result: '共同空闲', activity: '添加个人课表活动', saved: '操作已完成', semester_week: '设置当前周次',
      schedule: '小组日程安排', schedule_options: '候选时段', todos: '待办清单',
    }

    function snapshot(initial) {
      let value = initial
      const listeners = new Set()
      return {
        getSnapshot: () => value,
        subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener) },
        set(next) {
          value = next
          for (const listener of listeners) listener()
        },
      }
    }

    function createBoard(ctx) {
      const schedule = snapshot(null)
      const jobs = snapshot(new Map())
      const visible = snapshot(new Map())
      let pending
      function refresh(full = true) {
        if (pending) return pending
        const state = schedule.getSnapshot()
        pending = call(ctx, 'status', {
          full, signature: state?.signature || '', date: state?.date || '', undo_token: state?.undo?.token || '',
        })
          .then(response => {
            if (!response.ok) throw new Error(response.error)
            if (!response.value.cached) schedule.set(response.value)
          }).catch(error => {
            schedule.set({ ...state, note: `无法刷新课表。${errorText(error)}` })
          }).finally(() => { pending = null })
        return pending
      }
      return { schedule, jobs, visible, refresh }
    }

    const useSnapshot = store => useSyncExternalStore(store.subscribe, store.getSnapshot)

    function Monitor({ ctx, board }) {
      const session = useSnapshot(ctx.sidebarRight.mounted)
      const state = useSnapshot(board.schedule)
      const [now, setNow] = useState(Date.now())
      const [toast, setToast] = useState(null)
      const shown = useRef('')
      useEffect(() => {
        board.refresh()
        const interval = setInterval(() => {
          setNow(Date.now())
          if (document.visibilityState === 'visible') board.refresh(false)
        }, 1200)
        const focus = () => board.refresh()
        window.addEventListener('focus', focus)
        return () => { clearInterval(interval); window.removeEventListener('focus', focus) }
      }, [board])
      useEffect(() => {
        const next = state?.upcoming
        if (toast && (!next || toast.startsAt !== next.startsAt || toast.name !== next.name || now >= toast.startsAt)) setToast(null)
        if (!next?.startsAt || now >= next.startsAt || next.startsAt - now > 10 * 60_000) return
        const key = `${next.startsAt}/${next.name}/${next.room}`
        if (shown.current !== key) {
          shown.current = key
          setToast(next)
        }
      }, [now, state, toast])
      useEffect(() => {
        if (!session) return undefined
        let disposed = false
        let running = false
        async function poll() {
          if (running || document.visibilityState !== 'visible') return
          running = true
          try {
            const jobs = board.jobs.getSnapshot()
            const response = await call(ctx, 'job', { seen: jobs.get(session)?.id || '' }, session)
            if (disposed || ctx.sidebarRight.mounted.getSnapshot() !== session || !response.ok || !response.value) return
            const next = new Map(board.jobs.getSnapshot())
            next.delete(session)
            next.set(session, response.value)
            if (next.size > 30) next.delete(next.keys().next().value)
            board.jobs.set(next)
            ctx.sidebarRight.openTab(tabKind)
          } catch {
            // The Harness connection handles reconnection.
          } finally {
            running = false
          }
        }
        poll()
        const timer = setInterval(poll, 1000)
        return () => { disposed = true; clearInterval(timer) }
      }, [board, ctx, session])
      return toast && h('aside', { className: 'cf-ui cf-toast cf-v', role: 'status' },
        h('div', { className: 'cf-row cf-between' }, h('strong', null, '课前提醒'), button('知道了', () => setToast(null))),
        h('p', null, entry(toast)))
    }

    function ComposerButton({ ctx, board }) {
      const session = useSnapshot(ctx.sidebarRight.mounted)
      const visible = useSnapshot(board.visible)
      const tabId = [...visible].find(([, owner]) => owner === session)?.[0]
      const label = tabId ? '收起 CourseFlow 课表' : '打开 CourseFlow 课表'
      return h('button', { type: 'button', className: 'cf-composer', title: label, 'aria-label': label,
        'aria-pressed': Boolean(tabId), disabled: !session, onClick() {
          if (tabId) ctx.sidebarRight.hide(tabId)
          else ctx.sidebarRight.openTab(tabKind)
        } }, h(CalendarIcon))
    }

    function CourseFlowTab({ ctx, board, sessionId, useTabInfo }) {
      const { tab } = useTabInfo()
      useEffect(() => {
        if (!tab.visible) return undefined
        const current = new Map(board.visible.getSnapshot())
        current.set(tab.id, sessionId)
        board.visible.set(current)
        return () => {
          const next = new Map(board.visible.getSnapshot())
          next.delete(tab.id)
          board.visible.set(next)
        }
      }, [board, sessionId, tab.id, tab.visible])
      return h(Workspace, { key: sessionId, ctx, board, session: sessionId })
    }

    function AgendaOverview({ state, refresh, lookup, namedLookup, openSemesterWeek, busy }) {
      const [week, setWeek] = useState(null)
      const [course, setCourse] = useState('')
      const [now, setNow] = useState(Date.now())
      useEffect(() => {
        const timer = setInterval(() => setNow(Date.now()), 15_000)
        return () => clearInterval(timer)
      }, [])
      const next = state?.upcoming
      const countdown = next?.startsAt ? Math.ceil((next.startsAt - now) / 60_000) : 0
      const hasDates = Number.isInteger(state?.week)
      const currentWeek = state?.week > 0 && state.week <= state.weeks_total ? state.week : ''
      const queryWeek = week ?? (currentWeek || 1)
      return h('div', { className: 'cf-v' },
        h('div', { className: 'cf-row cf-between' },
          h('h2', null, '我的课表'), button('刷新课表', () => refresh())),
        state?.present && h('p', { className: 'cf-muted' }, [state.term, currentWeek && `第 ${currentWeek} 周`, state.source].filter(Boolean).join(' · ')),
        note(state?.note || (state ? !state.present && '请在 CourseFlow 保存课表，或在侧栏导入。' : '正在读取课表…')),
        hasDates && h('div', { className: 'cf-next' }, h('h3', null, '下一节课'),
          h('strong', null, next ? (next.kind === 'activity' ? `组队 · ${next.name}` : next.name) : '暂无后续课程'),
          next && h('p', { className: 'cf-muted' }, [next.date, next.clock || `${next.start}-${next.end} 节`, next.room,
            countdown > 0 && countdown < 1440 && `${countdown} 分钟后`].filter(Boolean).join(' · '))),
        hasDates && h('div', { className: 'cf-v' }, h('h3', null, '今日安排'), h(CourseList, { courses: state.today })),
        state?.present && h('form', { className: 'cf-row cf-week', onSubmit(event) {
          event.preventDefault()
          if (queryWeek) lookup(Number(queryWeek))
        } },
          h('label', { className: 'cf-row' }, '查看第', h('input', { type: 'number', min: 1, max: state.weeks_total, 'aria-label': '周次',
            value: queryWeek, onChange: event => setWeek(event.target.value) }), '周'),
          h('button', { type: 'submit', disabled: busy || !queryWeek }, '查看周课表'),
          button('设置当前周次', openSemesterWeek, false, busy)),
        state?.present && h('form', { className: 'cf-row', onSubmit(event) {
          event.preventDefault()
          if (course.trim() && !busy) namedLookup(course.trim())
        } }, field('按课名查下一次', course, setCourse, { placeholder: '例如 数据结构', maxLength: 120, required: true }),
          h('button', { type: 'submit', disabled: busy || !course.trim() }, '查下一次课')))
    }

    function SemesterWeek({ data, submit, busy }) {
      const [week, setWeek] = useState(data.suggested_week ?? data.current_week ?? '')
      const number = Number(week)
      const valid = Number.isInteger(number) && number >= 1 && number <= data.weeks_total
      const monday = Date.parse(`${data.monday}T00:00:00Z`)
      const start = valid ? new Date(monday - (number - 1) * 7 * 86_400_000).toISOString().slice(0, 10) : ''
      return h('form', { className: 'cf-v', onSubmit(event) {
        event.preventDefault()
        if (valid && !busy) return submit(number)
      } },
      h('p', { className: 'cf-muted' }, `按 ${data.today} 所在的一周计算，之后每周一自动更新周次。`),
      field('当前是第几周', week, setWeek, { type: 'number', min: 1, max: data.weeks_total, required: true }),
      start && h('p', { className: 'cf-note', 'aria-live': 'polite' }, `第 1 周周一将设为 ${start}。`),
      h('div', { className: 'cf-row' },
        h('button', { type: 'submit', className: 'cf-primary', disabled: busy || !valid }, '保存周次')))
    }

    function CourseList({ courses }) {
      if (!courses?.length) return h('p', { className: 'cf-muted' }, '无已确认课程')
      return h('ul', { className: 'cf-day-list' }, courses.map((item, index) => h('li', { key: index },
        h('span', { className: 'cf-muted' }, item.clock || `${item.start === item.end ? item.start : `${item.start}-${item.end}`} 节`),
        h('strong', null, item.kind === 'activity' ? `组队 · ${item.name}` : item.name), h('span', null, item.room))))
    }

    const periodLabel = item => `${item.start === item.end ? item.start : `${item.start}-${item.end}`} 节`
    const courseLabel = item => item.kind === 'activity' ? `组队 · ${item.name}` : item.name

    function WeekGridColumn({ day, today }) {
      const ends = []
      const items = day.courses.map((item, i) => {
        let lane = ends.findIndex(end => end < item.start)
        if (lane < 0) lane = ends.length
        ends[lane] = item.end
        return h('div', { key: i, className: 'cf-week-lesson', title: entry(item),
          style: { gridColumn: lane + 1, gridRow: `${item.start + 1} / ${item.end + 2}` } },
          h('strong', null, courseLabel(item)), h('span', null, item.room))
      })
      return h('div', { className: 'cf-week-column' + (day.date && day.date === today ? ' cf-today' : ''),
        style: { gridTemplateColumns: `repeat(${Math.max(1, ends.length)},minmax(0,1fr))` } },
        h('strong', { className: 'cf-week-heading', style: { gridColumn: '1/-1' } }, day.label, h('small', null, day.date?.slice(5))),
        ...Array.from({ length: 12 }, (_, i) => h('span', { key: `row${i}`, className: 'cf-week-period', style: { gridRow: i + 2 } })),
        ...items)
    }

    function WeekAgenda({ data, today, mode, setMode }) {
      const dateRange = data.days[0].date && `${data.days[0].date} – ${data.days[6].date}`
      return h('div', { className: 'cf-v' },
        h('div', { className: 'cf-row' }, h('h3', null, `第 ${data.week} 周`), dateRange && h('span', { className: 'cf-muted' }, dateRange)),
        h('div', { className: 'cf-row', role: 'group', 'aria-label': '课表视图' }, ...[['day', '按日卡片'], ['week', '周课表网格']].map(([id, label]) =>
          h('button', { key: id, type: 'button', 'aria-pressed': mode === id, className: mode === id ? 'cf-primary' : undefined,
            onClick: () => setMode(id) }, label))), note(data.warnings.join(' / ')),
        mode === 'week' ? h('div', { className: 'cf-scroll', tabIndex: 0, 'aria-label': '按星期和节次排列的课表' },
          h('div', { className: 'cf-week-grid' }, h('div', { className: 'cf-week-column' }, h('strong', { className: 'cf-week-heading' }, '节次'),
            ...Array.from({ length: 12 }, (_, i) => h('span', { key: i, className: 'cf-week-period' }, i + 1))),
          ...data.days.map(day => h(WeekGridColumn, { key: day.label, day, today })))) :
          data.days.map(day => h('section', { key: day.label, className: 'cf-day' + (day.date && day.date === today ? ' cf-today' : '') },
            h('h3', null, day.label, h('small', null, day.date?.slice(5)), day.date && day.date === today && h('small', null, '今天')),
            day.courses.length ? h('ul', { className: 'cf-day-list' }, ...day.courses.map((item, i) => h('li', { key: i },
              h('span', { className: 'cf-course-period', title: item.clock || undefined }, periodLabel(item)),
              h('strong', null, courseLabel(item)), h('span', { className: 'cf-course-room' }, item.room)))) :
              h('p', { className: 'cf-muted' }, '无已确认课程'))))
    }

    const acceptedTables = '.yaml,.yml,.xlsx,.csv,.docx,.pdf,.txt,image/png,image/jpeg,image/webp,image/gif'

    function readLocalFile(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve({ name: file.name, base64: String(reader.result).split(',')[1] })
        reader.onerror = () => reject(reader.error)
        reader.readAsDataURL(file)
      })
    }

    function WallpaperBackgroundPreview({ ctx, background, format, file }) {
      const [preview, setPreview] = useState(null)
      const cache = useRef(new Map())
      const custom = background === 'custom'
      const selection = custom ? file : `${background}/${format}`
      useEffect(() => {
        if (!selection) return undefined
        if (custom) {
          const src = URL.createObjectURL(file)
          setPreview({ selection, src })
          return () => URL.revokeObjectURL(src)
        }
        const cached = cache.current.get(selection)
        if (cached) {
          setPreview({ selection, src: cached })
          return undefined
        }
        let active = true
        call(ctx, 'wallpaper_background_preview', { background, format }).then(response => {
          if (!response.ok) throw new Error(response.error)
          const src = `data:image/png;base64,${response.value.base64}`
          cache.current.set(selection, src)
          if (active) setPreview({ selection, src })
        }).catch(error => {
          if (active) setPreview({ selection, error: errorText(error) })
        })
        return () => { active = false }
      }, [ctx, custom, file, background, format, selection])

      const image = preview?.selection === selection ? preview : null
      const label = custom ? file?.name : wallpaperPresets[background]
      return h('figure', { className: 'cf-background-preview', 'aria-label': '背景预览' }, image?.src
        ? h('img', { src: image.src, alt: `${label}的背景预览`, decoding: 'async', onError() {
          cache.current.delete(selection)
          setPreview({ selection, error: '这张图片无法预览。' })
        } })
        : h('p', { className: 'cf-muted', role: 'status' },
          image?.error || (selection ? '正在加载背景预览…' : '选择背景图片后即可预览。')))
    }

    function WorkbenchForm({ ctx, view, present, submit, onError, busy }) {
      const [text, setText] = useState('')
      const [files, setFiles] = useState([])
      const [groupSources, setGroupSources] = useState([])
      const [own, setOwn] = useState(false)
      const [outputs, setOutputs] = useState(['yaml'])
      const [light, setLight] = useState(false)
      const [background, setBackground] = useState('dusk')
      const [backgroundFile, setBackgroundFile] = useState(null)
      const backgroundPicker = useRef(null)
      const [reading, setReading] = useState(false)
      const importView = view === 'import'
      const adjustView = view === 'adjust'
      const groupView = view === 'group'
      const exportView = view === 'export'
      const wallpaper = exportView && outputs.some(format => format === 'desktop' || format === 'phone')
      const custom = wallpaper && background === 'custom'
      const attachments = groupView ? groupSources.filter(source => source.file).map(source => source.file) : files
      const shortcodePattern = /CF1\.[A-Za-z0-9_-]+\.[0-9a-fA-F]{8}/g
      const pastedCodes = groupView ? text.match(shortcodePattern) || [] : []
      const disabled = busy || reading || importView && !files.length || adjustView && (!present || !text.trim()) ||
        groupView && !groupSources.length && !pastedCodes.length && !own || exportView && (!present || !outputs.length) || custom && !backgroundFile
      const labels = { import: '读取课表', adjust: '校对调课信息', group: '下一步', export: '校对导出内容' }
      function addFiles(event) {
        const selected = [...event.target.files]
        if (!groupView) setFiles(selected)
        else {
          setGroupSources(current => [...current, ...selected.map(file => ({ file }))])
          event.target.value = ''
        }
      }
      function addCodes() {
        setGroupSources(current => {
          const fresh = [...new Set(pastedCodes)].filter(code => !current.some(source => source.code === code))
          return [...current, ...fresh.map(code => ({ code }))]
        })
        setText(text.replace(shortcodePattern, '').trim())
        onError('')
      }
      async function send(searchNow) {
        if (disabled) return
        if (attachments.length > 20 || attachments.reduce((size, file) => size + file.size, 0) > maxAttachmentBytes) {
          onError('附件合计最多 12 MB、20 份。大文件可用聊天里的 /courseflow 命令。')
          return
        }
        if (custom && backgroundFile.size > maxAttachmentBytes) {
          onError('背景图片最多 12 MB，请选择较小的图片。')
          return
        }
        setReading(true)
        try {
          const data = await Promise.all(attachments.map(readLocalFile))
          const payload = { mode: view, text, files: data }
          if (groupView) Object.assign(payload, {
            include_self: own, search_now: searchNow,
            shortcodes: groupSources.filter(source => source.code).map(source => source.code),
            member_order: groupSources.map(source => source.file ? 'file' : 'code'),
          })
          if (exportView) {
            payload.formats = outputs
            payload.text = light ? '浅色' : ''
          }
          if (wallpaper) {
            payload.wallpaper = { background }
            if (custom) payload.wallpaper.image = await readLocalFile(backgroundFile)
          }
          await submit('request', payload)
        } catch (error) {
          onError(errorText(error))
        } finally {
          setReading(false)
        }
      }
      return h('form', { className: 'cf-v', onSubmit(event) {
        event.preventDefault()
        send(true)
      } },
        h('h2', null, { import: '导入课表', adjust: '通知调课', group: '查找共同空闲', export: '导出课表' }[view]),
        !present && (adjustView || exportView) && note('请先打开或导入一份课表。'),
        importView && h('p', { className: 'cf-muted' }, '选择课表文件或截图，校对并确认后保存到我的课表。'),
        groupView && h('p', { className: 'cf-muted' }, '可以逐份选文件或添加 CF1 短码。成员资料加齐后点「下一步」一起查。'),
        (importView || groupView) && h('label', { className: 'cf-field' }, importView ? '选择课表文件' : '添加成员课表或忙闲卡', h('input', {
          type: 'file', multiple: groupView, accept: groupView ? `${acceptedTables},.busycard` : acceptedTables,
          disabled: busy || reading, onChange: addFiles,
        })),
        (adjustView || groupView) && h('label', { className: 'cf-field' }, adjustView ? '调课通知' : '忙闲卡短码或查询要求',
          h('textarea', { rows: 3, value: text, onChange: event => setText(event.target.value),
            placeholder: adjustView ? '把第 7 周周二的体育课调整到第 9 周周五下午两点，时长和地点不变' : '粘贴 CF1 短码，可附上「查第 7 周，至少连续 2 小节」' })),
        groupView && h('div', { className: 'cf-row' }, button('添加短码', addCodes, false, busy || reading || !pastedCodes.length)),
        groupView && groupSources.length > 0 && h('fieldset', { className: 'cf-v' }, h('legend', null, `已添加 ${groupSources.length} 份资料`),
          ...groupSources.map((source, index) => h('div', { className: 'cf-row cf-between', key: index },
            h('span', null, source.file?.name || `忙闲卡短码 ${index + 1}`),
            button('移除', () => setGroupSources(current => current.filter((_, i) => i !== index)), false, busy || reading)))),
        groupView && present && h('div', null, check('加入我的课表', own, setOwn),
          h('p', { className: 'cf-muted' }, '勾选后，查找空档时也会避开你在课表上已有的安排。')),
        exportView && h('fieldset', { className: 'cf-grid2' }, h('legend', null, '导出格式'),
          ...Object.entries(formats).map(([format, label]) => h('div', { key: format }, check(label, outputs.includes(format),
            checked => setOutputs(checked ? [...outputs, format] : outputs.filter(value => value !== format)))))),
        wallpaper && h('fieldset', { className: 'cf-v', disabled: busy || reading }, h('legend', null, '壁纸背景'),
          h('label', { className: 'cf-field' }, '选择背景', h('select', { value: background, onChange: event => {
            setBackground(event.target.value)
            setBackgroundFile(null)
            onError('')
          } }, h('optgroup', { label: '内置背景' }, Object.entries(wallpaperPresets).map(([id, label]) => h('option', { key: id, value: id }, label))),
          h('option', { value: 'custom' }, '使用本地图片'))),
          custom && h('div', { className: 'cf-row' },
            button('选择背景图片', () => backgroundPicker.current?.click()),
            backgroundFile && h('span', { className: 'cf-muted' }, backgroundFile.name),
            h('input', { type: 'file', ref: backgroundPicker, hidden: true, accept: '.png,.jpg,.jpeg,.webp,.bmp', onChange: event => {
              if (event.target.files[0]) setBackgroundFile(event.target.files[0])
              onError('')
            } })),
          check('浅色壁纸', light, setLight),
          h('p', { className: 'cf-muted' }, '校对课表后点「预览导出」，即可查看叠好课表的壁纸。')),
        h('div', { className: 'cf-row' },
          h('button', { type: 'submit', className: 'cf-primary', disabled }, labels[view]),
          groupView && button('核对成员', () => send(false), false, disabled),
          groupView && button('导出点格页', () => submit('request', { text: '导出点格页' }), false, busy || reading)),
        wallpaper && h(WallpaperBackgroundPreview, { ctx, background, format: outputs.includes('desktop') ? 'desktop' : 'phone',
          file: backgroundFile }))
    }

    function TodoList({ data, submit, reserve, busy }) {
      const [title, setTitle] = useState('')
      const [due, setDue] = useState('')
      const [course, setCourse] = useState('')
      async function add(event) {
        event.preventDefault()
        if (title.trim() && !busy && await submit({ operation: 'add', title, due, course })) {
          setTitle('')
          setDue('')
          setCourse('')
        }
      }
      return h('div', { className: 'cf-v' }, note(data.message, 'cf-ok'),
        h('form', { className: 'cf-v', onSubmit: add }, field('待办名称', title, setTitle, { required: true, maxLength: 120 }),
          h('div', { className: 'cf-grid2' }, field('截止日期 (选填)', due, setDue, { type: 'date' }),
            field('关联课程 (选填)', course, setCourse, { maxLength: 120 })),
          h('button', { type: 'submit', className: 'cf-primary', disabled: busy || !title.trim() }, '添加待办')),
        data.items.some(item => !item.done) && h('p', { className: 'cf-muted' },
          '「留出时间」会打开组队。选好空档并确认后，待办会作为活动写入课表。'),
        data.items.length ? data.items.map(item => h('section', { key: item.id, className: `cf-task cf-v ${item.done ? 'cf-task-complete' : ''}` },
          h('label', null, h('input', { type: 'checkbox', checked: item.done, disabled: busy,
            onChange: e => submit({ operation: 'complete', id: item.id, done: e.target.checked }) }), item.title),
          (item.due || item.course) && h('p', { className: 'cf-muted' }, [item.due && `截止 ${item.due}`, item.course].filter(Boolean).join(' · ')),
          h('div', { className: 'cf-row' }, !item.done && button('留出时间', () => reserve(item), false, busy),
            button('删除', () => submit({ operation: 'remove', id: item.id }), false, busy)))) :
          h('p', { className: 'cf-muted' }, '还没有待办.'))
    }

    function scheduleFields(draft) {
      return { ...draft, prep: draft.prep.map(item => ({ ...item, ownersText: item.owners.join(' / ') })) }
    }

    function schedulePayload(draft) {
      return { ...draft, prep: draft.prep.map(({ title, ownersText }) => ({ title,
        owners: ownersText.split(/[/,\uff0c\u3001]/).map(name => name.trim()).filter(Boolean) })) }
    }

    function ScheduleFields({ draft, change }) {
      const set = (key, value) => change({ ...draft, [key]: value })
      const row = (key, index, patch) => set(key, draft[key].map((item, i) => i === index ? { ...item, ...patch } : item))
      const remove = (key, index) => set(key, draft[key].filter((_, i) => i !== index))
      return h('div', { className: 'cf-v' },
        h('div', { className: 'cf-grid3' }, field('日期', draft.date, value => set('date', value), { type: 'date', required: true }),
          field('开始', draft.start, value => set('start', value), { type: 'time', required: true }),
          field('结束', draft.end, value => set('end', value), { type: 'time', required: true })),
        field('事项', draft.title, value => set('title', value), { maxLength: 120 }),
        field('集合地点', draft.room, value => set('room', value), { maxLength: 120 }),
        field('说明', draft.notes, value => set('notes', value), { maxLength: 240 }),
        h('details', null, h('summary', null, '成员名称或代号'), h('div', { className: 'cf-grid2' },
          ...draft.members.map((member, index) => h('div', { key: index }, field(`成员 ${index + 1}`, member,
            value => set('members', draft.members.map((name, i) => i === index ? value : name)), { maxLength: 80 }))))),
        h('fieldset', { className: 'cf-v' }, h('legend', null, '现场议程'),
          ...draft.agenda.map((item, index) => h('div', { className: 'cf-plan-row', key: index },
            field('分钟', item.minutes || '', value => row('agenda', index, { minutes: Number(value) }), { type: 'number', min: 1, max: 1440 }),
            field('议程内容', item.title, value => row('agenda', index, { title: value }), { maxLength: 120 }),
            button('移除', () => remove('agenda', index)))),
          button('添加一段议程', () => set('agenda', [...draft.agenda, { minutes: 10, title: '' }]), false, draft.agenda.length >= 12)),
        h('fieldset', { className: 'cf-v' }, h('legend', null, '会前分工'),
          ...draft.prep.map((item, index) => h('div', { className: 'cf-plan-row', key: index },
            field('负责人', item.ownersText, value => row('prep', index, { ownersText: value }), { placeholder: '甲 / 乙' }),
            field('准备事项', item.title, value => row('prep', index, { title: value }), { maxLength: 120 }),
            button('移除', () => remove('prep', index)))),
          button('添加一项分工', () => set('prep', [...draft.prep, { title: '', ownersText: '待分配' }]), false, draft.prep.length >= 12)))
    }

    function PlanSummary({ draft }) {
      return h('div', { className: 'cf-v' }, h('strong', null, draft.title || '未填写事项'),
        h('span', null, `${draft.date} ${draft.start}–${draft.end}`), h('span', null, `地点 ${draft.room || '待定'}`),
        draft.notes && h('p', null, draft.notes),
        draft.agenda.length > 0 && h('div', null, h('h3', null, '现场议程'), ...draft.agenda.map((item, i) =>
          h('p', { key: i }, `${item.minutes} 分钟 · ${item.title}`))),
        draft.prep.length > 0 && h('div', null, h('h3', null, '会前分工'), ...draft.prep.map((item, i) =>
          h('p', { key: i }, `${item.owners.join(' / ')} · ${item.title}`))))
    }

    function ScheduleOptions({ data, choose, back, busy }) {
      return h('div', { className: 'cf-v' },
        h('h3', null, `${data.title} · 需要 ${data.minutes} 分钟`), note(data.message), note(data.warnings.join(' / ')),
        !data.options.length && note('在现有忙闲资料和截止时间内没有可用候选. 可以调整日期或补充成员资料.'),
        ...data.options.map((item, index) => {
          const label = String.fromCharCode(65 + index)
          const shorter = item.kind === 'shorter'
          const duration = (Date.parse(`${item.date}T${item.end}:00Z`) - Date.parse(`${item.date}T${item.start}:00Z`)) / 60_000
          const description = item.kind === 'preferred' ? '符合偏好时段' : shorter ? `缩短到 ${duration} 分钟` : '换时段, 保留完整时长'
          return h('section', { className: 'cf-option cf-v' + (item.kind === 'preferred' ? ' cf-preferred' : ''), key: index },
            h('strong', null, `方案 ${label} · ${item.date} ${item.start}–${item.end}`), h('p', null, description),
            button(shorter ? `接受缩短并选方案 ${label}` : `选方案 ${label}`, () => choose(index, shorter), false, busy))
        }), button('返回组队结果', back, false, busy))
    }

    function ScheduleEditor({ data, submit, back, ctx, onError, busy }) {
      const [draft, setDraft] = useState(() => scheduleFields(data.review?.draft || data.draft))
      const [request, setRequest] = useState('')
      const [style, setStyle] = useState(data.style || 'green')
      const go = (operation, extra = {}) => submit({ token: data.token, operation, ...extra })
      if (data.review) return h('div', { className: 'cf-v' },
        h('p', null, `你的要求 · ${data.review.request}`), note(data.review.summary),
        h('div', { className: 'cf-compare' }, h('div', { className: 'cf-v' }, h('h3', null, '修改前'), h(PlanSummary, { draft: data.draft })),
          h('div', { className: 'cf-v' }, h('h3', null, '修改后 (可编辑)'), h(ScheduleFields, { draft, change: setDraft }))),
        h('div', { className: 'cf-row' }, button('取消修改', () => go('discard'), false, busy),
          button('应用修改', () => go('apply', { draft: schedulePayload(draft) }), true, busy)))
      return h('div', { className: 'cf-v' }, note(data.selection_note), note(data.message, 'cf-ok'),
        h(FileList, { files: data.files, ctx, onError }),
        data.preview ? h('div', { className: 'cf-v' }, h('h3', null, '日程卡预览'),
          h('img', { className: 'cf-plan-preview', src: `data:image/png;base64,${data.preview}`, alt: `日程卡 ${data.draft.title}` })) :
          h(ScheduleFields, { draft, change: setDraft }),
        h('p', { className: 'cf-muted' }, '日程卡用于分享。要留出个人课表时间，请回到组队，在「点选空档后」选择「添加个人课表活动」。'),
        !data.preview && h('fieldset', { className: 'cf-v' }, h('legend', null, 'AI 议程草稿'),
          h('p', { className: 'cf-muted' }, '可直接描述想做什么。AI 会补齐空白的事项，生成议程和分工。'),
          h('textarea', { 'aria-label': '日程目标或改动要求', value: request, onChange: e => setRequest(e.target.value),
            placeholder: '描述要做什么，可写上集合地点和准备要求', maxLength: 2000 }),
          h('div', { className: 'cf-row' }, ...[['suggest', 'AI 拟议程'], ['revise', 'AI 改日程']].map(([operation, name]) =>
            h('button', { key: operation, type: 'button', disabled: busy || !request.trim(),
              onClick: () => go(operation, { text: request, draft: schedulePayload(draft) }) }, name)))),
        h('label', { className: 'cf-field' }, '日程卡样式', h('select', { value: style, disabled: busy, onChange: e => {
          const value = e.target.value
          setStyle(value)
          if (data.preview) go('preview', { style: value })
        } }, ...Object.entries(scheduleStyles).map(([key, value]) => h('option', { key, value: key }, value)))),
        h('div', { className: 'cf-row' }, button('返回组队结果', back, false, busy),
          data.has_undo && button('撤销更改', () => go('undo'), false, busy),
          data.preview ? button('继续编辑', () => go('current'), false, busy) :
            button('保存草稿', () => go('save', { draft: schedulePayload(draft) }), false, busy),
          data.preview ? button('确认并导出 PNG', () => go('export', { style }), true, busy) :
            button('预览日程卡', () => go('preview', { style, draft: schedulePayload(draft) }), true, busy || !draft.title.trim())))
    }

    function Workspace({ ctx, board, session }) {
      const state = useSnapshot(board.schedule)
      const job = useSnapshot(board.jobs).get(session)
      const [view, setView] = useState('agenda')
      const [work, setWork] = useState(null)
      const [groupWork, setGroupWork] = useState(null)
      const [scheduleWork, setScheduleWork] = useState(null)
      const [settingsOpen, setSettingsOpen] = useState(false)
      const [busy, setBusy] = useState(false)
      const [error, setError] = useState('')
      const [paused, setPaused] = useState(null)
      const [weekMode, setWeekMode] = useState('day')
      const [task, setTask] = useState(null)
      const [preferPair, setPreferPair] = useState(true)
      const [groupTarget, setGroupTarget] = useState('schedule')
      const preparation = useRef(null)
      const edits = useRef(null)
      const group = useRef(null)
      const seen = useRef(null)
      const busyRef = useRef(false)

      function receive(response, resume) {
        if (!response.ok) {
          setError(response.error)
          if (response.code === 'ai_settings') {
            setPaused(resume || null)
            setSettingsOpen(true)
          }
          return
        }
        const next = response.value
        if (!next) return
        setError('')
        setSettingsOpen(next.type === 'settings')
        if (next.type === 'settings') {
          setPaused(null)
          return
        }
        if (next.type === 'prepare') {
          preparation.current = next
          edits.current = null
          setView(next.change ? 'adjust' : next.imported ? 'import' : 'export')
        }
        if (next.type === 'open_view') {
          setView(next.view)
          setWork(null)
          if (next.refresh) board.refresh()
          return
        }
        if (next.type === 'agenda') {
          setView('agenda')
          if (next.view_mode) setWeekMode(next.view_mode)
        }
        if (next.type === 'todos') setView('todos')
        if (next.group?.type === 'group_result') group.current = next.group
        if (next.type === 'todo_reserve') {
          setTask(next.item)
          setView('group')
          setWork(null)
          if (group.current?.token === next.group_token) setGroupWork(group.current)
          else if (next.group_token) {
            return call(ctx, 'group_refresh', { token: next.group_token }, session)
              .then(result => receive(result)).catch(error => setError(errorText(error)))
          } else setGroupWork(null)
          return
        }
        if (['schedule', 'schedule_options', 'schedule_empty'].includes(next.type)) {
          if (next.activity_token && group.current?.token === next.group_token) setGroupWork(group.current)
          setWork(null)
          setView('schedule')
          setScheduleWork(next)
        } else if (['group_prepare', 'group_result', 'activity'].includes(next.type) ||
            next.type === 'saved' && (next.group_token || next.return_group)) {
          if (next.type === 'group_result') group.current = next
          if (next.type === 'activity') {
            setTask(next.task)
          }
          if (next.updated && next.group_token) setTask(null)
          setWork(null)
          setView('group')
          setGroupWork(next)
        } else setWork(next)
        if (next.updated) board.refresh()
      }

      useEffect(() => {
        if (!job || busy || seen.current === job.id) return
        seen.current = job.id
        setPaused(null)
        setWork(null)
        receive(job, { action: 'resume', payload: { job: job.id } })
      }, [job, busy])

      async function submit(action, payload) {
        if (busyRef.current) return
        busyRef.current = true
        setBusy(true)
        setError('')
        try {
          const response = await call(ctx, action, payload, session)
          if (action === 'undo') {
            const current = board.schedule.getSnapshot()
            if (current?.undo?.token === payload.token) board.schedule.set({ ...current, undo: null })
            if (!response.ok) board.refresh()
          }
          await receive(response, { action, payload })
          return response.ok
        } catch (error) {
          setError(errorText(error))
          return false
        } finally {
          busyRef.current = false
          setBusy(false)
        }
      }

      function doPreview(fields, selected) {
        edits.current = { ...fields }
        submit('preview', { token: preparation.current.token, ...fields, selected })
      }
      function resume() {
        if (!paused) return
        const { action, payload } = paused
        setPaused(null)
        setSettingsOpen(false)
        if (action === 'preview') setWork(preparation.current)
        submit(action, payload)
      }
      function navigate(next) {
        setView(next)
        setWork(null)
        setSettingsOpen(false)
        setPaused(null)
        setError('')
        if (next === 'todos') submit('todos', {})
        if (next === 'schedule' && !scheduleWork) submit('schedule', { operation: 'current' })
      }
      function settings() {
        if (settingsOpen) setPaused(null)
        setSettingsOpen(!settingsOpen)
        setError('')
      }
      function lookupWeek(week) {
        return submit('request', { mode: 'agenda', week })
      }

      function startSchedule(fields, token = group.current?.token) {
        return submit('schedule', { operation: 'start', group_token: token,
          day: fields.day, first: fields.start, last: fields.end })
      }

      function reserve(item) {
        return submit('todo_reserve', { id: item.id })
      }

      function backToGroup(token) {
        if (group.current && group.current.token === token) {
          setView('group')
          setWork(null)
          setGroupWork(group.current)
        } else if (token) submit('group_refresh', { token })
        else navigate('group')
      }

      function renderPanel(work) {
        if (!work) return null
        switch (work.type) {
          case 'semester_week': return h(SemesterWeek, { key: work.token, data: work, busy,
            submit: week => submit('save_semester_week', { token: work.token, week }) })
          case 'agenda': return work.days ? h(WeekAgenda, { data: work, today: state?.date, mode: weekMode, setMode: setWeekMode }) :
            h('pre', { className: 'cf-listline' }, work.message || entry(work.upcoming) || '暂无已确认的下一节课。')
          case 'command_help': return h('pre', { className: 'cf-listline' }, work.message)
          case 'background_preview': return h('figure', { className: 'cf-background-preview' },
            h('img', { src: `data:image/png;base64,${work.base64}`, alt: work.message }), note(work.message))
          case 'prepare': return h(Preparation, { key: work.token, data: { ...work,
            table: edits.current ? { ...work.table, ...edits.current } : work.table },
            submit: fields => doPreview(fields), busy })
          case 'preview': return h(Preview, { key: work.confirmation || work.token, data: work,
            back: () => setWork(preparation.current),
            select: selected => doPreview(edits.current, selected), apply: token => submit('commit', { token }), busy })
          case 'group_prepare': return h(GroupReview, { key: work.token, data: work, timetable: state, busy,
            submit: data => submit('group_search', data) })
          case 'activity': {
            const back = () => backToGroup(work.group_token)
            if (work.open_schedule) return h(ActivityClocks, { key: work.token, slot: work, busy, back,
              submit: clocks => submit('activity_clocks', { slot: work.token, clocks }) })
            const selection = [work.date, work.fields.start, work.fields.end, work.task?.id].join('/')
            return h(Activity, { key: selection, slot: work, busy, back, present: state?.present,
              plan: () => startSchedule(work.fields, work.group_token),
              setGroupClocks: clocks => submit('activity_clocks', { slot: work.token, clocks }),
              submit: data => submit('activity', { slot: work.token, title: data.title, room: data.room, export_ics: data.export_ics }) })
          }
          case 'todos': return h(TodoList, { data: work, submit: fields => submit('todos', fields), reserve, busy })
          case 'schedule_empty': return h('div', { className: 'cf-v' },
            note('从组队结果选一段空档, 或在聊天中用 /courseflow 约事.'), button('打开组队', () => navigate('group'), false, busy))
          case 'schedule_options': return h(ScheduleOptions, { data: work, busy, back: () => backToGroup(work.group_token),
            choose: (index, shorter) => submit('schedule', { operation: 'choose', token: work.token, index, confirm_shorter: shorter }) })
          case 'schedule': return h(ScheduleEditor, { key: work.token, data: work, ctx, busy, onError: setError,
            back: () => backToGroup(work.group_token), submit: fields => submit('schedule', fields) })
          case 'saved': return h('div', { className: 'cf-v' },
            note(work.message, 'cf-ok'), h(FileList, { files: work.files, ctx, onError: setError }),
            (work.group_token || work.return_group) && button('返回忙闲图', () => {
              if (work.group_token) submit('group_refresh', { token: work.group_token })
              else backToGroup(group.current?.token)
            }, false, busy))
          default: return null
        }
      }

      function heading(work, back) {
        const title = panelTitles[work?.type]
        if (!title) return null
        const weekly = work.type === 'agenda' && work.days
        return h('div', { className: 'cf-row cf-between' },
          h('div', { className: 'cf-row' }, h('h2', null, work.needs_clocks || work.edit_clocks ? '确认组队作息' : title),
            weekly && h('div', { className: 'cf-row', role: 'group', 'aria-label': '切换周次' },
              button('上一周', () => lookupWeek(work.week - 1), false, busy || work.week <= 1),
              button('下一周', () => lookupWeek(work.week + 1), false, busy || work.week >= work.weeks_total))),
          back && button(work.type === 'group_result' ? '重新查询' : '返回', back, false, busy))
      }

      const showGroup = view === 'group' && !settingsOpen && !work
      const showSchedule = view === 'schedule' && !settingsOpen && !work
      const groupResult = group.current
      const groupBack = ['group_prepare', 'group_result'].includes(groupWork?.type) ? () => setGroupWork(null) : null
      const panel = renderPanel(work)
      const notices = [
        error ? h('p', { key: 'error', role: 'alert', className: 'cf-error' }, error) : null,
        busy ? h('p', { key: 'busy', role: 'status', className: 'cf-note' }, '处理中…') : null,
      ]
      const formProps = { ctx, present: state?.present, submit, busy, onError: setError }

      return h('section', { className: 'cf-ui cf-pane', 'aria-label': 'CourseFlow 课表' },
        h('header', { className: 'cf-pane-header' },
          h('nav', { className: 'cf-nav', 'aria-label': 'CourseFlow 功能' }, Object.entries(sections).map(([id, title]) => h('button', {
            key: id, type: 'button', 'aria-current': view === id && !settingsOpen ? 'page' : undefined,
            disabled: busy, onClick: () => navigate(id),
          }, title))),
          h('div', { className: 'cf-row' },
            h('button', { type: 'button', disabled: busy || !state?.undo, onClick: () => submit('undo', { token: state.undo.token }),
              title: state?.undo ? `撤销上一次${state.undo.label}` : '当前没有可撤销的课表改动' }, '撤销上一步'),
            h('button', { type: 'button', className: 'cf-icon', title: 'AI 接口设置', 'aria-label': 'AI 接口设置',
              'aria-pressed': settingsOpen, disabled: busy, onClick: settings }, h(GearIcon)))),
        h('div', { className: 'cf-pane-body cf-v', hidden: !showGroup },
          showGroup && notices,
          task && note(`为 ${task.title} 留时间. 请选择共同空档并确认写入课表.`),
          heading(groupWork, groupBack),
          renderPanel(groupWork),
          h('div', { hidden: groupWork?.type !== 'group_result' }, groupResult && h(Heatmap, {
            key: groupResult.token, data: groupResult, preferPair, setPreferPair, busy, task,
            target: groupTarget, setTarget: setGroupTarget,
            exportGrid: () => submit('point_grid', { token: groupResult.token }),
            select: fields => submit('activity_preview', { group_token: groupResult.token, todo_id: task?.id || null,
              open_schedule: !task && groupTarget !== 'personal', edit_clocks: !task && groupTarget === 'clocks', ...fields }),
          })),
          h('div', { hidden: Boolean(groupWork) }, h(WorkbenchForm, { ...formProps, view: 'group' }))),
        h('div', { className: 'cf-pane-body cf-v', hidden: !showSchedule },
          showSchedule && notices, heading(scheduleWork), renderPanel(scheduleWork),
          !scheduleWork && button('打开当前日程', () => submit('schedule', { operation: 'current' }), false, busy)),
        settingsOpen && h('div', { className: 'cf-pane-body cf-v' }, notices,
          h(Settings, { ctx, onResume: paused ? resume : undefined, onSaved: () => setError('') })),
        !showGroup && !showSchedule && !settingsOpen && h('div', { className: 'cf-pane-body cf-v' },
          notices, heading(work, work?.type === 'todos' ? null : () => navigate(view)), panel,
          view === 'agenda' && !panel && h(AgendaOverview, { state, refresh: board.refresh, busy, lookup: lookupWeek,
            namedLookup: name => submit('request', { mode: 'agenda', text: `下次${name}在哪上` }),
            openSemesterWeek: () => submit('semester_week', {}) }),
          view === 'todos' && !panel && button('刷新待办', () => submit('todos', {}), false, busy),
          ['import', 'adjust', 'export'].includes(view) && (!panel || view === 'export') && h('div', { hidden: Boolean(panel) },
            h(WorkbenchForm, { key: view, ...formProps, view }))))
    }

    function apply(ctx) {
      if (!ctx.connection.isLoopback) return
      const board = createBoard(ctx)
      ctx.effect(() => {
        const sheet = document.createElement('style')
        sheet.textContent = css
        document.head.append(sheet)
        return () => sheet.remove()
      }, 'CourseFlow styles')
      ctx.effect(() => ctx.sidebarRightTabs.register({ id: plugin, kind: tabKind,
        title: () => 'CourseFlow 课表', keepMounted: true,
        guide: [{ id: tabKind, order: 60, title: () => 'CourseFlow 课表', icon: CalendarIcon }],
      }), 'CourseFlow right sidebar')
      ctx.slots.inject('sidebar.right.pane.tab', () => ctx.slots.register({
        name: 'sidebar.right.pane.tab', key: plugin,
      }, props => h(CourseFlowTab, { ...props, ctx, board })))
      ctx.slots.inject('conversation.input.left', () => ctx.slots.register({
        name: 'conversation.input.left', id: 'courseflow.toggle',
      }, () => h(ComposerButton, { ctx, board })))
      ctx.slots.inject('shell.overlay', () => ctx.slots.register({
        name: 'shell.overlay', id: 'courseflow.reminders',
      }, () => h(Monitor, { ctx, board })))
      ctx.slots.inject('plugins.bundle.config', () => ctx.slots.register({
        name: 'plugins.bundle.config', key: 'dsh-courseflow',
      }, props => props.view === 'page' ? h(Settings, { ctx }) : null))
      ctx.effect(() => ctx.inputTriggers.registerSource({
        trigger: '@', name: 'CourseFlow', order: -1, showGroupTitle: false,
        async candidates(_session, { query, quoted }) {
          return !quoted && ('courseflow 我的课表'.includes(query.toLowerCase()))
            ? [{ name: 'CourseFlow', label: 'CourseFlow · 我的课表', description: '查课、调课或找共同空闲', value: 'courseflow' }]
            : []
        },
        onPick({ position }) {
          return { text: position === 'leading' ? '/courseflow ' : '用 CourseFlow ' }
        },
      }), 'CourseFlow mention')
    }

    return { apply, inject: ['slots', 'connection', 'inputTriggers', 'sidebarRight', 'sidebarRightTabs'] }
  },
})

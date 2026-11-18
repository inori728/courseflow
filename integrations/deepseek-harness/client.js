window.__ModuleLoader__.load({
  id: 'dsh-courseflow',
  factory(require) {
    const { createElement: h, useEffect, useRef, useState, useSyncExternalStore } = require('react')
    const plugin = 'dsh-courseflow'
    const tabKind = 'courseflow'
    const sections = { agenda: '课表', import: '导入', adjust: '调课', group: '组队', export: '导出' }
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    const formats = { desktop: '电脑壁纸', phone: '手机壁纸', yaml: '课表 YAML', ics: '日历 ICS', pdf: 'A4 PDF', png: '挂图 PNG' }
    const wallpaperPresets = { dusk: '黄昏晚霞', night: '深夜星河', sea: '海盐渐变', purple: '暮紫渐变' }
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
      .cf-background-preview{margin:0;overflow:hidden;border:1px solid var(--cf-line);border-radius:9px}.cf-background-preview img{display:block;width:100%;height:auto;max-height:300px;object-fit:contain}.cf-background-preview>p{padding:10px 12px}
      .cf-toast{position:absolute;top:52px;right:20px;width:308px;max-width:calc(100vw - 40px);background:var(--cf-bg);border:1px solid var(--cf-line);border-radius:12px;box-shadow:0 5px 24px #1925541a;padding:14px}
      .cf-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.cf-between{justify-content:space-between}.cf-v{display:grid;gap:10px;min-width:0}.cf-muted{opacity:.75}.cf-note,.cf-error,.cf-ok{border-radius:8px;padding:8px 10px}.cf-note{background:#e9edff;color:#283d92}.cf-error{background:#fff0f0;color:#9b232d}.cf-ok{background:#e5f7eb;color:#20583b}.cf-ui summary{cursor:pointer}.cf-ui details[open]>summary{margin-bottom:8px}
      .cf-next{border:1px solid var(--cf-line);border-left:3px solid var(--cf-accent);border-radius:9px;padding:10px 12px;display:grid;gap:3px}.cf-day-list{list-style:none;margin:0;padding:0}.cf-day-list li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding:6px 0;border-bottom:1px solid var(--cf-line)}.cf-ui .cf-week input{width:68px}
      .cf-grid2,.cf-grid3,.cf-grid4{display:grid;gap:8px}.cf-grid2{grid-template-columns:repeat(2,minmax(0,1fr))}.cf-grid3{grid-template-columns:repeat(3,minmax(0,1fr))}.cf-grid4{grid-template-columns:repeat(4,minmax(0,1fr))}
      .cf-field{display:grid;gap:4px}.cf-table{border-collapse:collapse;width:100%;min-width:440px}.cf-table td,.cf-table th{border-bottom:1px solid var(--cf-line);padding:5px 3px;text-align:left}.cf-table td:first-child{min-width:112px}.cf-scroll{overflow:auto;max-height:420px}.cf-grid-heat{display:grid;grid-template-columns:minmax(76px,1fr) repeat(7,minmax(43px,1fr));gap:4px;align-items:center;min-width:405px;text-align:center}
      .cf-grid-heat .cf-free{background:#daf3e6;color:#1d5339;border:1px solid transparent;padding:5px 2px}.cf-grid-heat .cf-busy{background:#e4eafe;color:#2c487c;border-radius:7px;padding:5px 2px}.cf-grid-heat small{display:block}.cf-compare{display:grid;grid-template-columns:1fr 1fr;gap:8px}.cf-compare>div{border:1px solid var(--cf-line);padding:8px;border-radius:8px}.cf-listline{white-space:pre-wrap;overflow-wrap:anywhere;margin:0;font:inherit}
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
        h('div', { className: 'cf-row' }, button('返回核对', back, false, busy),
          data.confirmation && button(data.overwrite ? data.change ? '确认调课' : '确认导入' : '确认生成',
            () => apply(data.confirmation), true, busy || chosen)),
      )
    }

    function GroupReview({ data, submit, busy }) {
      const [members, setMembers] = useState(data.members)
      const [week, setWeek] = useState(data.week)
      const [minimum, setMinimum] = useState(data.minutes || data.minimum)
      const [minutes, setMinutes] = useState(Boolean(data.minutes))
      const [own, setOwn] = useState(data.include_self)
      const update = (i, value) => setMembers(members.map((member, index) => index === i ? value : member))
      return h('div', { className: 'cf-v' },
        h('p', { className: 'cf-muted' }, '核对成员与学期。查询周次以第一位上传成员为准。'),
        ...members.map((member, i) => h('fieldset', { key: i, className: 'cf-v' },
          field('成员名称', member.name, name => update(i, { ...member, name }), { maxLength: 80 }),
          member.courses ? h(TableEditor, { table: member, setTable: value => update(i, value) }) :
            h('p', { className: 'cf-muted' }, `第 1 周周一 ${member.start} · 已提供第 ${member.weeks.join('、')} 周`))),
        data.can_include_self && check('加入我已保存的课表', own, setOwn),
        h('div', { className: 'cf-grid3' },
          field('查询周次', week, setWeek, { type: 'number', min: 1, max: 104 }),
          field(minutes ? '最少分钟数' : '最少连续小节', minimum, setMinimum, { type: 'number', min: 1, max: minutes ? 1440 : 12 }),
          check('按分钟筛选', minutes, setMinutes)),
        button('查找共同空闲', () => submit({ token: data.token, members: members.map(member => ({
          name: member.name, ...(member.courses ? tableEdits(member) : {}),
        })), week: Number(week), minimum: minutes ? 1 : Number(minimum), minutes: minutes ? Number(minimum) : 0, include_self: own }), true, busy || !week || !minimum),
      )
    }

    function Heatmap({ data, select, exportGrid, busy }) {
      const labelSlot = (day, first, last) => {
        const start = data.clocks[first]?.split('-')[0]
        const end = data.clocks[last]?.split('-')[1]
        return `${data.dates[day]} ${days[day]} · ${first === last ? first : `${first}-${last}`} 节${start && end ? ` · ${start}–${end}` : ''}`
      }
      return h('div', { className: 'cf-v' },
        h('p', { className: 'cf-muted' }, `第 ${data.week} 周 · ${data.names.join('、')}`),
        note(data.warnings?.join(' / ')),
        h('div', { className: 'cf-row' }, button('导出点格页', exportGrid, false, busy)),
        h('details', { open: !data.windows.length || undefined },
          h('summary', null, `符合条件的连续空闲时段（${data.windows.length}）`),
          h('div', { className: 'cf-v' }, ...data.windows.map((item, i) => h('button', {
            key: i, type: 'button', onClick: () => select(item, labelSlot(item.day, item.start, item.end)),
          }, labelSlot(item.day, item.start, item.end))))),
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
                  title: labelSlot(j, i + 1, i + 1), disabled: !data.clocks[i + 1],
                  onClick: () => select({ day: j, start: i + 1, end: i + 1 }, labelSlot(j, i + 1, i + 1)),
                }, '空闲')
            }),
          ]).flat(),
        )),
      )
    }

    function Activity({ slot, back, submit, busy }) {
      const [title, setTitle] = useState('')
      const [place, setPlace] = useState('')
      const [exportIcs, setExportIcs] = useState(false)
      return h('form', { className: 'cf-v', onSubmit(event) {
        event.preventDefault()
        if (title.trim()) submit({ ...slot.fields, title, room: place, export_ics: exportIcs })
      } },
      note(slot.label),
      field('活动名称', title, setTitle, { autoFocus: true, required: true, maxLength: 120 }),
      field('地点（选填）', place, setPlace, { maxLength: 120 }),
      check('同时导出会议 ICS', exportIcs, setExportIcs),
      h('div', { className: 'cf-row' }, button('返回忙闲图', back, false, busy),
        h('button', { type: 'submit', className: 'cf-primary', disabled: busy || !title.trim() }, '保存到我的课表')))
    }

    const panelTitles = {
      prepare: '校对课表', preview: '操作预览', agenda: '课程查询', group_prepare: '核对组队资料',
      group_result: '共同空闲', activity: '添加事件', saved: '操作已完成', semester_week: '设置当前周次',
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
      return h(Workspace, { ctx, board, session: sessionId })
    }

    function AgendaOverview({ state, refresh, lookup, openSemesterWeek, busy }) {
      const [week, setWeek] = useState(null)
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
          button('设置当前周次', openSemesterWeek, false, busy)))
    }

    function SemesterWeek({ data, submit, busy }) {
      const [week, setWeek] = useState(data.current_week ?? '')
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

    function WeekAgenda({ data }) {
      return h('div', { className: 'cf-v' }, h('h3', null, `第 ${data.week} 周`), note(data.warnings.join(' / ')),
        ...data.days.map(day => h('section', { key: day.label },
          h('div', { className: 'cf-row' }, h('strong', null, day.label), h('span', { className: 'cf-muted' }, day.date)),
          h(CourseList, { courses: day.courses }))))
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
      const disabled = busy || reading || importView && !files.length || adjustView && (!present || !text.trim()) ||
        groupView && !files.length && !text.trim() && !own || exportView && (!present || !outputs.length) || custom && !backgroundFile
      const labels = { import: '读取课表', adjust: '校对调课信息', group: '核对成员', export: '校对导出内容' }
      async function send(event) {
        event.preventDefault()
        if (disabled) return
        if (files.length > 20 || files.reduce((size, file) => size + file.size, 0) > maxAttachmentBytes) {
          onError('附件合计最多 12 MB、20 份。大文件可用聊天里的 /courseflow 命令。')
          return
        }
        if (custom && backgroundFile.size > maxAttachmentBytes) {
          onError('背景图片最多 12 MB，请选择较小的图片。')
          return
        }
        setReading(true)
        try {
          const data = await Promise.all(files.map(readLocalFile))
          const payload = { mode: view, text, files: data }
          if (groupView) payload.include_self = own
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
      return h('form', { className: 'cf-v', onSubmit: send },
        h('h2', null, { import: '导入课表', adjust: '通知调课', group: '查找共同空闲', export: '导出课表' }[view]),
        !present && (adjustView || exportView) && note('请先打开或导入一份课表。'),
        importView && h('p', { className: 'cf-muted' }, '选择课表文件或截图，校对并确认后保存到我的课表。'),
        (importView || groupView) && h('label', { className: 'cf-field' }, importView ? '选择课表文件' : '添加成员课表或忙闲卡', h('input', {
          type: 'file', multiple: groupView, accept: groupView ? `${acceptedTables},.busycard` : acceptedTables,
          onChange: event => setFiles([...event.target.files]),
        })),
        (adjustView || groupView) && h('label', { className: 'cf-field' }, adjustView ? '调课通知' : '忙闲卡短码或查询要求',
          h('textarea', { rows: 3, value: text, onChange: event => setText(event.target.value),
            placeholder: adjustView ? '把第 7 周周二的体育课调整到第 9 周周五下午两点，时长和地点不变' : '粘贴 CF1 短码，可附上「查第 7 周，至少连续 2 小节」' })),
        groupView && present && check('加入我的课表', own, setOwn),
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
          check('浅色壁纸', light, setLight)),
        h('div', { className: 'cf-row' },
          h('button', { type: 'submit', className: 'cf-primary', disabled }, labels[view]),
          groupView && button('导出点格页', () => submit('request', { text: '导出点格页' }), false, busy || reading)),
        wallpaper && h(WallpaperBackgroundPreview, { ctx, background, format: outputs.includes('desktop') ? 'desktop' : 'phone',
          file: backgroundFile }))
    }

    function Workspace({ ctx, board, session }) {
      const state = useSnapshot(board.schedule)
      const job = useSnapshot(board.jobs).get(session)
      const [view, setView] = useState('agenda')
      const [work, setWork] = useState(null)
      const [busy, setBusy] = useState(false)
      const [error, setError] = useState('')
      const [paused, setPaused] = useState(null)
      const preparation = useRef(null)
      const edits = useRef(null)
      const previous = useRef(null)
      const group = useRef(null)
      const seen = useRef(null)
      const busyRef = useRef(false)

      function receive(response, resume) {
        if (!response.ok) {
          setError(response.error)
          if (response.code === 'ai_settings') {
            setPaused(resume || null)
            setWork({ type: 'settings' })
          }
          return
        }
        const next = response.value
        if (!next) return
        setError('')
        if (next.type === 'prepare') {
          preparation.current = next
          edits.current = null
          setView(next.change ? 'adjust' : next.imported ? 'import' : 'export')
        }
        if (next.type === 'agenda') setView('agenda')
        if (next.type === 'group_prepare') {
          group.current = null
          setView('group')
        }
        if (next.type === 'group_result') group.current = next
        setWork(next)
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
          receive(response, { action, payload })
        } catch (error) {
          setError(errorText(error))
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
        setWork(action === 'preview' ? preparation.current : null)
        submit(action, payload)
      }
      function navigate(next) {
        setView(next)
        setWork(null)
        setPaused(null)
        setError('')
      }
      function settings() {
        if (work?.type === 'settings') {
          setWork(previous.current)
          setPaused(null)
        } else {
          previous.current = work
          setWork({ type: 'settings' })
        }
        setError('')
      }
      function lookupWeek(week) {
        return submit('request', { mode: 'agenda', week })
      }

      const weeklyResult = work?.type === 'agenda' && work.days
      const panel = work && (() => {
        switch (work.type) {
          case 'settings': return h(Settings, { ctx, onResume: paused ? resume : undefined, onSaved: () => setError('') })
          case 'semester_week': return h(SemesterWeek, { key: work.token, data: work, busy,
            submit: week => submit('save_semester_week', { token: work.token, week }) })
          case 'agenda': return work.days ? h(WeekAgenda, { data: work }) :
            h('pre', { className: 'cf-listline' }, work.message || entry(work.upcoming) || '暂无已确认的下一节课。')
          case 'prepare': return h(Preparation, { key: work.token, data: { ...work,
            table: edits.current ? { ...work.table, ...edits.current } : work.table },
            submit: fields => doPreview(fields), busy })
          case 'preview': return h(Preview, { key: work.confirmation || work.token, data: work,
            back: () => setWork(preparation.current),
            select: selected => doPreview(edits.current, selected), apply: token => submit('commit', { token }), busy })
          case 'group_prepare': return h(GroupReview, { key: work.token, data: work, busy, submit: data => submit('group_search', data) })
          case 'group_result': return h(Heatmap, { data: work, busy, exportGrid: () => submit('point_grid', { token: work.token }),
            select: (fields, label) => setWork({ type: 'activity', fields, label }) })
          case 'activity': return h(Activity, { slot: work, busy, back: () => setWork(group.current),
            submit: data => submit('activity', { token: group.current.token, ...data }) })
          case 'saved': return h('div', { className: 'cf-v' },
            note(work.message, 'cf-ok'), h(FileList, { files: work.files, ctx, onError: setError }),
            (work.group_token || work.return_group) && button('返回忙闲图', () => {
              if (work.group_token) submit('group_refresh', { token: work.group_token })
              else setWork(group.current)
            }, false, busy))
          default: return null
        }
      })()

      return h('section', { className: 'cf-ui cf-pane', 'aria-label': 'CourseFlow 课表' },
        h('header', { className: 'cf-pane-header' },
          h('nav', { className: 'cf-nav', 'aria-label': 'CourseFlow 功能' }, Object.entries(sections).map(([id, title]) => h('button', {
            key: id, type: 'button', 'aria-current': view === id && work?.type !== 'settings' ? 'page' : undefined,
            disabled: busy, onClick: () => navigate(id),
          }, title))),
          h('div', { className: 'cf-row' },
            h('button', { type: 'button', disabled: busy || !state?.undo, onClick: () => submit('undo', { token: state.undo.token }),
              title: state?.undo ? `撤销上一次${state.undo.label}` : '当前没有可撤销的课表改动' }, '撤销上一步'),
            h('button', { type: 'button', className: 'cf-icon', title: 'AI 接口设置', 'aria-label': 'AI 接口设置',
              'aria-pressed': work?.type === 'settings', disabled: busy, onClick: settings }, h(GearIcon)))),
        h('div', { className: 'cf-pane-body cf-v' },
          error && h('p', { role: 'alert', className: 'cf-error' }, error),
          busy && h('p', { role: 'status', className: 'cf-note' }, '处理中…'),
          work && panelTitles[work.type] && h('div', { className: 'cf-row cf-between' },
            h('div', { className: 'cf-row' }, h('h2', null, panelTitles[work.type]),
              weeklyResult && h('div', { className: 'cf-row', role: 'group', 'aria-label': '切换周次' },
                button('上一周', () => lookupWeek(work.week - 1), false, busy || work.week <= 1),
                button('下一周', () => lookupWeek(work.week + 1), false, busy || work.week >= work.weeks_total))),
            button('返回', () => navigate(view), false, busy)),
          panel,
          view === 'agenda' && !panel && h(AgendaOverview, { state, refresh: board.refresh, busy, lookup: lookupWeek,
            openSemesterWeek: () => submit('semester_week', {}) }),
          view !== 'agenda' && (!panel || view === 'export') && h('div', { hidden: Boolean(panel) },
            h(WorkbenchForm, { key: view, ctx, view, present: state?.present, submit, busy, onError: setError }))))
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

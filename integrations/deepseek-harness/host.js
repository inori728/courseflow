import { spawn } from 'node:child_process'
import { readFileSync, realpathSync, statSync } from 'node:fs'
import { readFile, stat, realpath } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const packageName = 'dsh-courseflow'
const courseflowRoot = resolve(dirname(realpathSync(fileURLToPath(import.meta.url))), '..', '..')
const dev = join(courseflowRoot, '.dev')
const python = process.env.COURSEFLOW_PYTHON || join(dev, 'venv', 'Scripts', 'python.exe')
const temp = join(dev, 'tmp')
const binding = readBinding()
const backend = process.env.COURSEFLOW_BACKEND || binding.backend
const home = process.env.COURSEFLOW_HOME || binding.dataDir || join(dev, 'user-data')
const workbenchOps = new Set(['preview', 'commit', 'undo', 'semester_week', 'save_semester_week', 'wallpaper_background_preview',
  'group_search', 'group_refresh', 'activity', 'point_grid'])
const tableFiles = new Set(['.yaml', '.yml', '.csv', '.xlsx', '.docx', '.pdf', '.busycard', '.txt'])
const imageSuffixes = { 'image/png': '.png', 'image/jpeg': '.jpg', 'image/webp': '.webp', 'image/gif': '.gif' }
const objectSchema = { type: 'object', additionalProperties: true }
const bundledApp = process.env.COURSEFLOW_HARNESS_APP || binding.appArchive || join(dirname(process.execPath), 'resources', 'app.asar')
const bundled = createRequire(join(bundledApp, 'dsh', 'package.json'))

function readBinding() {
  try {
    return JSON.parse(readFileSync(join(dev, 'courseflow-harness-binding.json'), 'utf8'))
  } catch (error) {
    if (error.code === 'ENOENT') return {}
    throw error
  }
}

async function harnessImport(specifier) {
  try {
    return await import(specifier)
  } catch (error) {
    if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error
    return import(pathToFileURL(bundled.resolve(specifier)).href)
  }
}

const [{ defineTool }, { createTypertRemoteInfo, TypertRemoteService }, { z }] = await Promise.all([
  harnessImport('@deepseek-ai/dsh-tools'),
  harnessImport('@deepseek-ai/dsh-typert-protocol'),
  harnessImport('zod'),
])
const inputCodec = {
  mode: 'strict', typeSymbol: 'dsh-courseflow#BoardInput',
  create: () => z.record(z.string(), z.json()), jsonSchema: objectSchema,
}
const remote = createTypertRemoteInfo({
  package: packageName,
  methods: {
    'courseflow/operate': {
      service: 'courseflow',
      invocation: { kind: 'direct' },
      parameters: [{ name: 'request', source: 'json', codec: inputCodec, strictCodec: inputCodec }],
      result: inputCodec,
    },
  },
}, z)

export const name = 'courseflow'
export const inject = ['commands', 'tools', 'attachments', 'typert']

function runCourseFlow(action, payload, signal) {
  if (signal?.aborted) return Promise.resolve({ ok: false, error: '操作已取消.' })
  return new Promise((accept) => {
    const finish = (value) => {
      clearTimeout(timeout)
      accept(value)
    }
    const executable = spawn(backend || python, backend ? [] : ['-m', 'courseflow.harness'], {
      cwd: courseflowRoot, windowsHide: true, signal,
      env: {
        ...process.env, COURSEFLOW_HOME: home, TEMP: temp, TMP: temp, PYTHONDONTWRITEBYTECODE: '1', PYTHONIOENCODING: 'utf-8',
        ...(action === 'status' ? { OPENBLAS_NUM_THREADS: '1' } : {}),
      },
      stdio: ['pipe', 'pipe', 'ignore'],
    })
    const failure = (error) => ({ ok: false, error })
    const timeout = setTimeout(() => executable.kill(), 240_000)
    let output = ''
    executable.stdout.setEncoding('utf8')
    executable.stdout.on('data', (chunk) => {
      output += chunk
      if (output.length > 8_000_000) executable.kill()
    })
    executable.stdin.on('error', () => {})
    executable.on('error', () => finish(failure(signal?.aborted
      ? '操作已取消.' : backend ? '无法启动随包附带的 CourseFlow，请核对便携目录是否完整。'
        : '无法启动 CourseFlow Python 环境. 请核对项目环境或 COURSEFLOW_PYTHON.')))
    executable.on('close', (code) => {
      if (code !== 0) {
        finish(failure('CourseFlow 操作未完成或超时, 请核对输入后重试.'))
        return
      }
      try {
        finish(JSON.parse(output))
      } catch {
        finish(failure('CourseFlow 返回了无法读取的结果.'))
      }
    })
    executable.stdin.end(JSON.stringify({ ...payload, action }), 'utf8')
  })
}

function latestUserAttachments(agent) {
  const session = agent.session
  const events = session.snapshotEvents(Math.max(0, session.seq - 120), session.seq)
  const message = [...events].reverse().find((event) => event.type === 'user/message' && event.data.source?.kind === 'user')
  return (message?.data.content ?? []).filter((block) => block.type === 'file' || block.type === 'image')
}

function attachmentFiles(store, blocks) {
  if (blocks.length > 20) throw new Error('每次最多添加 20 份成员资料.')
  return blocks.map((block, index) => {
    const image = block.type === 'image'
    const attachment = block.attachment
    const path = image ? store.imageHostPath(attachment) : store.fileHostPath(attachment)
    if (!path || !isAbsolute(path)) throw new Error('这份附件的本机文件不可用. 请重新添加.')
    let filename = attachment.name || `课表 ${index + 1}`
    if (image && !Object.values(imageSuffixes).includes(extname(filename).toLowerCase())) {
      filename += imageSuffixes[attachment.mediaType] || '.png'
    }
    return { name: filename, path }
  })
}

function browserFiles(files = []) {
  if (!Array.isArray(files) || files.length > 20) throw new Error('每次最多添加 20 份成员资料.')
  return files.map((file, index) => {
    const suffix = extname(String(file.name)).toLowerCase()
    if (!tableFiles.has(suffix) && !Object.values(imageSuffixes).includes(suffix)) throw new Error('请选择课表、图片或忙闲卡文件.')
    if (typeof file.base64 !== 'string' || file.base64.length > 20_000_000) throw new Error('附件过大, 请分批添加或用斜杠命令.')
    return { name: file.name || `附件 ${index + 1}`, base64: file.base64 }
  })
}

function stamp(file) {
  if (!file) return ''
  try {
    const info = statSync(file, { bigint: true })
    return `${info.mtimeNs}/${info.ctimeNs}/${info.size}/${info.ino}`
  } catch {
    return '-'
  }
}

async function exportFile(id) {
  if (typeof id !== 'string' || !/^[a-f0-9]{32}\/[^/\\:\x00-\x1f]+$/.test(id)) {
    throw new Error('请选择已导出的文件.')
  }
  const root = await realpath(join(home, 'harness', 'exports'))
  const filename = await realpath(resolve(root, id))
  const difference = relative(root, filename)
  if (difference.startsWith('..' + sep) || isAbsolute(difference)) throw new Error('无法读取导出目录以外的文件.')
  const info = await stat(filename)
  if (!info.isFile() || info.size > 16 * 1024 * 1024) {
    throw new Error('文件过大或已移动, 请从 CourseFlow 的本地导出目录打开.')
  }
  return { base64: (await readFile(filename)).toString('base64'), name: id.split('/')[1] }
}

class CourseFlowService extends TypertRemoteService {
  constructor(ctx) {
    super(ctx, 'courseflow')
    this.state = {
      jobs: new Map(),
      queue: Promise.resolve(),
      status: null,
      statusPending: null,
      statusGeneration: 0,
    }
  }

  async operate(request) {
    const invocation = this.ctx.invocation
    if (invocation?.peer.principal.kind !== 'owner') return { ok: false, error: '请从本机 Harness 打开 CourseFlow.' }
    const { action, payload = {}, session = '' } = request
    try {
      if (action === 'job') {
        const job = this.state.jobs.get(session)
        return { ok: true, value: job && job.id !== payload.seen ? job.response : null }
      }
      if (action === 'resume') {
        const job = this.state.jobs.get(session)
        if (!job || job.id !== payload.job) return { ok: false, error: '请重新发起这次课表操作.' }
        const result = await this.call('request', job.input, invocation.signal)
        if (this.state.jobs.get(session) === job) job.response = { id: job.id, ...result }
        return result
      }
      if (action === 'download') return { ok: true, value: await exportFile(payload.id) }
      if (action === 'status') return this.status(payload)
      if (action === 'settings' || action === 'save_settings') {
        return this.call(action, payload, invocation.signal)
      }
      if (action === 'request') {
        const { mode, text = '', week, formats, include_self, files, wallpaper } = payload
        return this.call('request', { mode, text, week, formats, include_self, wallpaper, files: browserFiles(files) }, invocation.signal)
      }
      if (workbenchOps.has(action)) {
        const { files, ...options } = payload
        return this.call(action, options, invocation.signal)
      }
      return { ok: false, error: '未知的 CourseFlow 操作.' }
    } catch (error) {
      return { ok: false, error: error.message }
    }
  }

  call(action, payload, signal) {
    if (!['commit', 'activity', 'undo', 'save_settings', 'save_semester_week'].includes(action)) return runCourseFlow(action, payload, signal)
    const work = this.state.queue.then(async () => {
      const response = await runCourseFlow(action, payload, signal)
      if (response.ok && response.value?.updated) {
        this.state.statusGeneration++
        this.state.status = null
      }
      return response
    })
    this.state.queue = work.catch(() => {})
    return work
  }

  async status(payload) {
    const current = this.state.status
    const files = value => [value.watch_path, value.watch_undo_path, join(home, 'session.json')].map(stamp).join('/')
    const before = current ? files(current.value) : null
    if (!payload.full && current && current.stamp === before && Date.now() < current.refreshAt) {
      const { watch_path, watch_undo_path, ...value } = current.value
      const undoToken = value.undo?.token || ''
      const cached = payload.signature === value.signature && payload.date === value.date && (payload.undo_token || '') === undoToken
      return { ok: true, value: cached
        ? { present: value.present, signature: value.signature, date: value.date, cached: true } : value }
    }
    this.state.statusPending ??= (async () => {
      const generation = this.state.statusGeneration
      const response = await runCourseFlow('status', { full: true })
      if (response.ok) {
        const value = response.value
        const after = files(value)
        if (generation === this.state.statusGeneration && (before === null || before === after)) {
          this.state.status = {
            value,
            stamp: after,
            refreshAt: Math.min(Date.now() + 600_000, value.next_day_at || Infinity, value.upcoming?.startsAt || Infinity),
          }
        }
      }
      return response
    })().finally(() => { this.state.statusPending = null })
    const response = await this.state.statusPending
    if (!response.ok) return response
    const { watch_path, watch_undo_path, ...value } = response.value
    return { ok: true, value }
  }

  publish(session, value, input) {
    this.state.jobs.delete(session)
    const id = randomUUID()
    this.state.jobs.set(session, { id, input, response: { id, ...value } })
    if (this.state.jobs.size > 30) this.state.jobs.delete(this.state.jobs.keys().next().value)
  }
}

const guidance = 'For CourseFlow requests call courseflow_request with the user instructions. It opens a local panel for imports, edits and grouped availability. The user completes the preview and confirmation in that panel. Do not edit schedule files directly; do not claim that a preview was saved. Use structured intent only if the user provided complete fields. Explicit ranges are small periods, paired big periods use 1-2, 3-4, etc. Ask the user to clarify a bare period number.';

function summary(response) {
  if (!response.ok) return response.error
  const value = response.value
  if (value.message) return value.message
  if (value.type === 'agenda') {
    const next = value.upcoming
    return next ? `${next.date} ${next.clock} ${next.name} ${next.room}`.trim() : '当前没有下一节已确认的课程.'
  }
  if (value.type === 'group_prepare') return '请在 CourseFlow 面板核对成员和周次, 然后查询共同空闲.'
  return '请在 CourseFlow 面板查看并确认本次操作.'
}

export function apply(ctx) {
  const board = new CourseFlowService(ctx)
  ctx.effect(() => ctx.typert.register({
    package: packageName, face: 'host', schemas: [], model: { services: [], types: [] },
    invocations: remote.descriptors,
  }))
  ctx.inject(['skills'], (scope) => {
    scope.skills.register({
      name: 'courseflow', description: 'Use CourseFlow for classes, schedule changes, wallpapers and team availability.',
      source: 'runtime', content: guidance, invocation: { modelInvocable: true, userInvocable: false },
    })
  })

  async function start(agent, text, blocks, args, signal) {
    const payload = { text, files: attachmentFiles(ctx.attachments, blocks), ...args }
    const response = await board.call('request', payload, signal)
    if (agent && !signal?.aborted) board.publish(agent.id, response, payload)
    return response
  }

  ctx.commands.register({
    name: 'courseflow',
    description: '用 CourseFlow 查课、调课、识图导出或查共同空闲',
    input: { hint: '输入课表指令, 可添加课表或忙闲卡', attachments: true },
    recordInput: false,
    async handler({ agent, rawInput, attachments, signal }) {
      const text = rawInput.trim()
      if (!text && !attachments.length) {
        return { kind: 'success', text: '示例: /courseflow 查今天的课, 或附上课表和忙闲卡查共同空闲.' }
      }
      try {
        const response = await start(agent, text, attachments, {}, signal)
        if (!response.ok && response.code !== 'ai_settings') return { kind: 'error', text: response.error }
        return { kind: 'success', text: summary(response) }
      } catch (error) {
        return { kind: 'error', text: error.message }
      }
    },
  })

  ctx.tools.register(defineTool({
    name: 'courseflow_request',
    description: guidance,
    parameters: {
      text: { type: 'string', required: true, description: 'User request including the desired action and time' },
      intent: { type: 'object', additionalProperties: true, description:
        'Optional structured adjustment with course_name, source_week, source_day and target fields. Weekdays 1-7, period ranges use small periods.' },
      formats: { type: 'array', items: { type: 'string', enum: ['yaml', 'ics', 'desktop', 'phone', 'pdf', 'png'] } },
    },
    timeoutMs: 245_000,
    output: { schema: { type: 'string' }, render: (_args, value) => [{ type: 'text', text: value }] },
    async execute({ text, intent, formats }, exec) {
      if (!exec.agent) return '请在 Harness 会话中发起课表操作.'
      const response = await start(exec.agent, text, latestUserAttachments(exec.agent), {
        ...(intent ? { intent } : {}), ...(formats ? { formats } : {}),
      }, exec.signal)
      return summary(response)
    },
  }))
}

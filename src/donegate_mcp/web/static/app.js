"use strict";

(() => {
  const $ = (selector) => document.querySelector(selector);
  const escape = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const labels = {draft:"草稿",ready:"待开始",in_progress:"进行中",awaiting_verification:"待验证",verified:"已验证",documented:"文档已同步",done:"已完成",blocked:"已阻塞",passed:"通过",failed:"失败",unknown:"未记录",synced:"已同步",pending:"待同步",outdated:"文档已过期",stale:"已过期",manual:"人工验证","self-test":"自测"};
  const statuses = ["draft","ready","in_progress","awaiting_verification","verified","documented","done","blocked"];
  const state = {projects:[], projectsLoaded:false, detail:null, route:null, sequence:0, filters:new Map(), open:new Set(), signatures:{}, lastSuccess:null, removing:null};
  const id = (task) => String(task.task_id ?? task.id ?? "");
  const projectName = (project) => project.project_name || project.project_id || project.key || "未命名项目";
  const projectURL = (key, view = "overview") => `/projects/${encodeURIComponent(key)}/${view}`;
  const date = (value, short = false) => {
    if (!value) return "暂无时间记录";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    return new Intl.DateTimeFormat("zh-CN", short ? {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"} : {year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).format(parsed);
  };
  const number = (value) => Number.isFinite(Number(value)) ? Number(value) : 0;
  const percent = (summary) => summary?.completion_rate == null ? "—" : `${Math.round(number(summary.completion_rate) * 10) / 10}%`;
  const badge = (value, label) => `<span class="badge ${Object.hasOwn(labels, value) ? escape(value) : value === "revalidation" ? "revalidation" : ""}">${escape(label || labels[value] || value || "未记录")}</span>`;
  const progress = (done, total, label) => `<div class="progress-track"><progress max="${Math.max(1, number(total))}" value="${Math.max(0, number(done))}" aria-label="${escape(label)}"></progress></div>`;
  const empty = (title, description, action = "", symbol = "▦") => `<div class="empty-state"><div class="empty-symbol" aria-hidden="true">${symbol}</div><h2>${escape(title)}</h2><p>${escape(description)}</p>${action}</div>`;
  const list = (values) => Array.isArray(values) && values.length ? `<ul class="code-list">${values.map(value => `<li><code>${escape(value)}</code></li>`).join("")}</ul>` : `<span class="muted">未设置</span>`;
  const field = (name, value, html = false) => `<div><dt>${escape(name)}</dt><dd>${html ? value : escape(value || "未记录")}</dd></div>`;
  const filters = () => {
    if (!state.filters.has(state.route.key)) state.filters.set(state.route.key, {query:"",status:"all"});
    return state.filters.get(state.route.key);
  };

  function readRoute() {
    const match = location.pathname.match(/^\/projects\/([^/]+)\/(overview|features|changes)\/?$/);
    if (match) {
      try { return {key:decodeURIComponent(match[1]), view:match[2]}; } catch (_) { /* handled as missing route */ }
    }
    return {key:null, view:location.pathname === "/" ? "portfolio" : "missing"};
  }

  // Restore keyboard focus and native details state when new facts change the content.
  // Search, status inputs and dialogs live outside this replaceable region.
  function replace(element, html, signatureKey) {
    if (state.signatures[signatureKey] === html) return;
    const active = document.activeElement;
    const focusKey = element.contains(active) ? active?.getAttribute("data-focus") : null;
    const focusIndex = focusKey ? [...element.querySelectorAll("[data-focus]")].filter(node => node.dataset.focus === focusKey).indexOf(active) : -1;
    element.innerHTML = html;
    state.signatures[signatureKey] = html;
    if (focusKey) {
      const candidates = [...element.querySelectorAll("[data-focus]")].filter(node => node.dataset.focus === focusKey);
      const replacement = candidates[focusIndex] || candidates[0];
      replacement?.focus({preventScroll:true});
    }
  }

  function notice(message = "", error = false) {
    $("#notice").innerHTML = message ? `<div class="notice ${error ? "error" : ""}">${escape(message)}</div>` : "";
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {cache:"no-store",...options,headers:{"Accept":"application/json",...(options.body ? {"Content-Type":"application/json"} : {}),...options.headers}});
    const body = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(body.error || `请求失败（${response.status}）`);
    return body;
  }

  function renderSidebar() {
    $("#project-count").textContent = state.projects.length;
    $(".portfolio-link").classList.toggle("active", state.route.view === "portfolio");
    if (state.route.view === "portfolio") $(".portfolio-link").setAttribute("aria-current", "page");
    else $(".portfolio-link").removeAttribute("aria-current");
    replace($("#project-nav"), state.projects.length ? state.projects.map(project => `<a class="nav-item ${state.route.key === project.key ? "active" : ""}" href="${projectURL(project.key)}" data-nav data-focus="nav-${escape(project.key)}" ${state.route.key === project.key ? 'aria-current="page"' : ""} title="${escape(project.repo_root)}"><span class="project-initial" aria-hidden="true">${escape(Array.from(projectName(project))[0].toUpperCase())}</span><span class="project-nav-label">${escape(projectName(project))}</span>${project.error ? '<span class="sidebar-error" aria-label="项目读取失败">!</span>' : ""}</a>`).join("") : '<p class="sidebar-empty">尚未登记项目</p>', "sidebar");
  }

  function renderHeading() {
    const route = state.route;
    const project = state.detail?.project || state.projects.find(item => item.key === route.key);
    const title = route.key ? projectName(project || {key:route.key}) : "所有项目";
    const viewLabel = {overview:"项目概览",features:"功能进度",changes:"需求变更",portfolio:"所有项目",missing:"页面不存在"}[route.view];
    document.title = `${route.key ? `${title} · ${viewLabel}` : viewLabel} · DoneGate`;
    $("#breadcrumb").textContent = route.key ? `工作空间 / ${title} / ${viewLabel}` : `工作空间 / ${viewLabel}`;
    replace($("#page-heading"), `<div class="page-heading"><div><span class="eyebrow">${route.key ? "PROJECT WORKSPACE" : "WORKSPACE PORTFOLIO"}</span><h1>${escape(route.view === "missing" ? "页面不存在" : title)}</h1><p>${route.key ? escape(project?.repo_root || "正在读取项目路径…") : "关注交付进度，追踪需求变化与验证证据。"}</p></div><div class="heading-actions">${route.key ? '<button type="button" class="subtle-button" data-action="remove" data-focus="remove-project">移除登记</button>' : '<button type="button" class="primary" data-action="add" data-focus="add-project">＋ 添加项目</button>'}</div></div>`, "heading");
    $("#view-tabs").hidden = !route.key;
    replace($("#view-tabs"), route.key ? [["overview","项目概览"],["features","功能进度"],["changes","需求变更"]].map(([view,label]) => `<a href="${projectURL(route.key, view)}" data-nav data-focus="tab-${view}" class="${view === route.view ? "active" : ""}" ${view === route.view ? 'aria-current="page"' : ""}>${label}</a>`).join("") : "", "tabs");
    $("#filter-bar").hidden = route.view !== "features" || !state.detail;
  }

  function metric(label, value, note, tone = "", unit = "") {
    return `<div class="metric ${tone}"><div class="metric-label">${escape(label)}</div><div class="metric-number">${escape(value)}${unit ? `<small>${escape(unit)}</small>` : ""}</div><div class="metric-note">${escape(note)}</div></div>`;
  }

  function renderPortfolio() {
    if (!state.projects.length) return empty("从第一个项目开始", "添加已初始化的 DoneGate 仓库，在这里汇总功能进度、验证状态与需求变更。", '<button class="primary" type="button" data-action="add">＋ 添加项目</button>');
    const usable = state.projects.filter(project => !project.error && project.summary);
    const sum = (key) => usable.reduce((total, project) => total + number(project.summary[key]), 0);
    const total = sum("total_tasks"), done = sum("done_tasks");
    return `<div class="metrics">${metric("已登记项目", state.projects.length, `${usable.length} 个可读取 · ${state.projects.length - usable.length} 个异常`)}${metric("已完成任务", done, "仅计入当前状态为已完成的任务", "teal", `/ ${total}`)}${metric("需要重新验证", sum("needs_revalidation"), "需求或输入变化后需重新确认", "amber")}${metric("阻塞任务", sum("blocked_tasks"), "等待解除阻塞的功能", "red")}</div><div class="section-heading"><h2>项目工作空间</h2><span>${state.projects.length} 个项目 · ${total} 个可读取任务</span></div><div class="project-grid">${state.projects.map(projectCard).join("")}</div>`;
  }

  function projectCard(project) {
    const summary = project.summary || {}, counts = summary.counts_by_status || {};
    return `<a class="project-card" href="${projectURL(project.key)}" data-nav data-focus="project-${escape(project.key)}"><div class="card-title"><span class="project-initial" aria-hidden="true">${escape(Array.from(projectName(project))[0].toUpperCase())}</span><div><h3>${escape(projectName(project))}</h3><small>${escape(project.repo_root)}</small></div><span class="card-arrow" aria-hidden="true">↗</span></div>${project.error ? `<div class="notice error">${escape(project.error)}</div><div class="card-footer">项目暂时无法读取 · 查看详情</div>` : `<div class="progress-label"><span>完成度 <strong>${percent(summary)}</strong></span><span><strong>${number(summary.done_tasks)}</strong> / ${number(summary.total_tasks)} 个任务已完成</span></div>${progress(summary.done_tasks, summary.total_tasks, `${number(summary.done_tasks)} / ${number(summary.total_tasks)} 个任务已完成`)}<div class="card-footer"><span><i class="status-dot in_progress" aria-hidden="true"></i>进行中 ${number(counts.in_progress)}</span><span><i class="status-dot needs_revalidation" aria-hidden="true"></i>待重验 ${number(summary.needs_revalidation)}</span><span><i class="status-dot blocked" aria-hidden="true"></i>阻塞 ${number(summary.blocked_tasks)}</span><span class="last-update">${escape(project.updated_at ? date(project.updated_at, true) : "暂无更新")}</span></div>`}</a>`;
  }

  function taskLink(taskId, text) {
    return `<a class="task-link" data-nav data-focus="task-link-${escape(taskId)}" href="${projectURL(state.route.key,"features")}?task=${encodeURIComponent(taskId)}">${escape(text || taskId)}</a>`;
  }

  function renderOverview() {
    const {summary = {},tasks = [],project = {}} = state.detail;
    const counts = summary.counts_by_status || {};
    const attention = tasks.filter(task => task.needs_revalidation || task.evidence_stale || task.status === "blocked");
    return `<div class="metrics">${metric("交付完成度", percent(summary), `${number(summary.done_tasks)} / ${number(summary.total_tasks)} 个任务已完成`, "teal")}${metric("管理任务", number(summary.total_tasks), "按需求文档组织的功能任务")}${metric("需要重新验证", number(summary.needs_revalidation), "独立于任务状态的验证提醒", "amber")}${metric("阻塞任务", number(summary.blocked_tasks), "查看阻塞原因与后续行动", "red")}</div><div class="overview-columns"><section class="panel"><div class="section-heading"><h2>完成状态分布</h2><span>${number(summary.done_tasks)} / ${number(summary.total_tasks)} 已完成</span></div>${number(summary.total_tasks) ? `<div class="distribution">${statuses.map(status => `<div class="distribution-row"><span>${labels[status]}</span>${progress(counts[status], summary.total_tasks, `${labels[status]} ${number(counts[status])} 个`)}<strong>${number(counts[status])}</strong></div>`).join("")}</div>` : '<p class="muted">项目尚无任务。添加任务后，这里会显示实际状态分布。</p>'}</section><section class="panel"><div class="section-heading"><h2>需要关注</h2><a href="${projectURL(state.route.key,"features")}" data-nav>查看功能 →</a></div>${attention.length ? `<div class="attention-list">${attention.slice(0,6).map(task => `<div class="attention-item"><div><h3>${taskLink(id(task),task.title || id(task))}</h3><p>${escape(task.blocked_reason || task.stale_reason || (task.evidence_stale ? "验证证据已过期，请重新验证当前输入。" : "需求或输入已变化，请重新验证当前实现。"))}</p></div>${badge(task.status === "blocked" ? "blocked" : "revalidation",task.status === "blocked" ? undefined : task.evidence_stale ? "证据已过期" : "待重验")}</div>`).join("")}</div>${attention.length > 6 ? `<p class="muted">另有 ${attention.length - 6} 个任务需要关注。</p>` : ""}` : '<div class="empty-state"><div class="empty-symbol" aria-hidden="true">✓</div><h2>当前没有阻塞或验证提醒</h2><p>验证和需求变化会反映在这里。</p></div>'}</section></div><section class="panel"><div class="section-heading"><h2>工作空间信息</h2><span>登记项目的实际路径</span></div><dl class="project-paths"><dt>项目标识</dt><dd>${escape(project.project_id || "未提供")}</dd><dt>仓库目录</dt><dd>${escape(project.repo_root)}</dd><dt>数据目录</dt><dd>${escape(project.data_root || "项目默认目录")}</dd><dt>最近更新</dt><dd>${escape(date(state.detail.updated_at))}</dd></dl></section>`;
  }

  function detailKey(kind, key) { return `${state.route.key}:${kind}:${key}`; }
  function openAttribute(key) { return state.open.has(key) ? " open" : ""; }

  function taskDetail(task) {
    const taskId = id(task), taskKey = detailKey("task", taskId), eventKey = detailKey("events", taskId);
    const events = Array.isArray(task.events) ? [...task.events].reverse() : [];
    return `<details class="task-item" data-open-key="${escape(taskKey)}" id="task-${escape(taskId)}"${openAttribute(taskKey)}><summary class="task-summary" data-focus="task-${escape(taskId)}"><span class="task-chevron" aria-hidden="true">›</span><div class="task-heading"><h3>${escape(task.title || "未命名功能")}</h3><small>${escape(taskId)}</small></div><div class="task-badges">${badge(task.status)}${task.needs_revalidation ? badge("revalidation","需要重新验证") : ""}${task.evidence_stale ? badge("revalidation","证据已过期") : ""}</div></summary><div class="task-detail">${task.summary ? `<p class="task-description">${escape(task.summary)}</p>` : ""}${task.blocked_reason ? `<div class="notice error">阻塞原因：${escape(task.blocked_reason)}</div>` : ""}${task.needs_revalidation || task.evidence_stale ? `<div class="notice">${escape(task.stale_reason || "当前输入已变化，已有验证证据需要重新确认。")}</div>` : ""}<div class="detail-grid"><section class="detail-section"><h4>验收协议</h4><dl class="detail-fields">${field("验证方式",labels[task.verification_mode] || task.verification_mode)}${field("测试命令",list(task.test_commands),true)}${field("要求文档",list(task.required_doc_refs),true)}${field("要求产物",list(task.required_artifacts),true)}${field("任务范围",list(task.owned_paths),true)}${field("需求版本",task.spec_version != null ? `v${task.spec_version}` : null)}</dl></section><section class="detail-section"><h4>验证与证据</h4><dl class="detail-fields">${field("验证结果",badge(task.verification_status),true)}${field("文档同步",badge(task.doc_sync_status),true)}${field("证据有效性",task.evidence_stale ? "已过期" : task.needs_revalidation ? "需要重新验证" : "未标记过期")}${field("验证引用",task.last_verification_ref)}${field("文档引用",task.last_doc_sync_ref)}${field("自测引用",task.last_self_test_ref)}${field("自测退出码",task.last_self_test_exit_code == null ? null : String(task.last_self_test_exit_code))}${field("最近更新",date(task.updated_at))}</dl></section></div><details class="events" data-open-key="${escape(eventKey)}"${openAttribute(eventKey)}><summary data-focus="events-${escape(taskId)}">事件记录 · ${events.length}</summary>${events.length ? `<ol class="event-list">${events.map(event => `<li><div class="event-meta"><strong>${escape(event.type)}</strong><time>${escape(date(event.timestamp))}</time><span>${escape(event.actor || "")}</span></div>${event.payload && Object.keys(event.payload).length ? `<pre>${escape(JSON.stringify(event.payload,null,2))}</pre>` : ""}</li>`).join("")}</ol>` : '<p class="muted">暂无事件记录</p>'}</details></div></details>`;
  }

  function renderFeatures() {
    const tasks = state.detail.tasks || [], {query,status} = filters();
    const search = query.trim().toLocaleLowerCase();
    const filtered = tasks.filter(task => (status === "all" || (status === "needs_revalidation" ? task.needs_revalidation : task.status === status)) && [task.title,id(task),task.summary,task.spec_ref].some(value => String(value || "").toLocaleLowerCase().includes(search)));
    $("#filter-count").textContent = `${filtered.length} / ${tasks.length} 个功能`;
    if (!tasks.length) return empty("还没有功能任务", "使用 DoneGate CLI 或 MCP 创建任务后，这里将按需求文档展示功能和验收证据。", "", "☷");
    if (!filtered.length) return empty("没有匹配的功能", "尝试其他关键词，或清除状态筛选。", '<button class="secondary" data-action="clear-filter" type="button">清除筛选</button>', "⌕");
    const groups = new Map();
    for (const task of filtered) {
      const spec = task.spec_ref || "未关联需求文档";
      if (!groups.has(spec)) groups.set(spec, []);
      groups.get(spec).push(task);
    }
    return [...groups].map(([spec,items]) => `<section class="spec-group"><div class="spec-heading"><span aria-hidden="true">▤</span><h2>${escape(spec)}</h2><span>${items.length} 个功能</span></div><div class="task-list">${items.map(taskDetail).join("")}</div></section>`).join("");
  }

  function diffHTML(diff) {
    return `<pre class="diff" aria-label="需求文本差异">${String(diff).split("\n").map(line => `<span class="diff-line ${line.startsWith("+") && !line.startsWith("+++") ? "addition" : line.startsWith("-") && !line.startsWith("---") ? "deletion" : line.startsWith("@@") ? "hunk" : ""}">${escape(line)}</span>`).join("\n")}</pre>`;
  }

  function renderChanges() {
    const changes = [...(state.detail.changes || [])].sort((a,b) => String(b.timestamp || "").localeCompare(String(a.timestamp || "")));
    if (!changes.length) return empty("暂无已记录的需求变更", "引用需求时建立的快照、显式刷新与偏离声明会出现在这里。未记录的文件编辑不会自动生成历史。", "", "↳");
    return `<p class="timeline-intro">${changes.length} 条已记录历史 · 需求快照、漂移事件与偏离声明。仅相邻且有文本的快照可展示差异。</p><div class="timeline">${changes.map((change,index) => {
      const key = detailKey("change",change.id || index);
      const baseline = change.kind === "snapshot" && number(change.version) === 1;
      const kind = {snapshot:baseline ? "初始快照" : "需求快照",spec_drift:"需求漂移",deviation:"偏离声明"}[change.kind] || change.kind;
      const body = change.kind === "deviation" ? (change.content ? `<pre>${escape(change.content)}</pre>` : `<p class="muted">未记录偏离详情。</p>`) : change.diff != null ? diffHTML(change.diff) : baseline && change.content != null ? `<p class="muted">初始版本，暂无前一版本可比较。</p><pre>${escape(change.content)}</pre>` : `<p class="muted">${baseline ? "初始版本，暂无前一版本可比较。" : "此历史未保存可比较的相邻文本，无法还原差异。"}</p>`;
      return `<article class="change-card"><div class="change-meta"><time>${escape(date(change.timestamp))}</time><span>·</span><span>${escape(kind)}</span>${change.version != null ? `<span class="badge">${change.previous_version != null ? `v${escape(change.previous_version)} → ` : ""}v${escape(change.version)}</span>` : ""}</div><div class="panel"><div class="change-title"><h3>${escape(change.spec_ref || "未关联需求文档")}</h3></div><p class="change-reason">${escape(change.reason || (baseline ? "首次建立需求内容基线。" : "未记录变更原因。"))}</p><div class="affected"><span>影响任务</span>${change.affected_task_ids?.length ? change.affected_task_ids.map(taskId => taskLink(taskId)).join("") : '<span>无已记录的关联任务</span>'}</div>${change.previous_hash || change.current_hash ? `<div class="hashes"><span>内容哈希 </span><code>${escape(change.previous_hash || "无前一版本")} → ${escape(change.current_hash || "未记录")}</code></div>` : ""}<details class="diff-details" data-open-key="${escape(key)}"${openAttribute(key)}><summary data-focus="change-${escape(change.id || index)}">${change.kind === "deviation" ? "查看偏离详情" : change.diff != null ? "查看文本差异" : baseline && change.content != null ? "查看初始内容" : "历史文本说明"}</summary>${body}</details></div></article>`;
    }).join("")}</div>`;
  }

  function renderContent() {
    renderHeading();
    let html;
    if (state.route.view === "portfolio" && !state.projectsLoaded) return;
    else if (state.route.view === "portfolio") html = renderPortfolio();
    else if (state.route.view === "missing") html = empty("找不到这个页面", "请从项目列表选择一个工作空间。", '<a class="primary" href="/" data-nav>返回所有项目</a>');
    else if (!state.detail) return;
    else html = state.route.view === "overview" ? renderOverview() : state.route.view === "features" ? renderFeatures() : renderChanges();
    replace($("#content"), html, "content");
    $("#content").setAttribute("aria-busy", "false");
  }

  let pollTimer = null;
  let activeRefresh = null;
  let manualRefreshQueued = false;

  function cancelRefresh() {
    ++state.sequence;
    window.clearTimeout(pollTimer);
    pollTimer = null;
    manualRefreshQueued = false;
    activeRefresh?.controller.abort();
    activeRefresh = null;
  }

  // Start the next polling delay only after both reads finish. Slow workspaces
  // therefore have one outstanding batch, and their responses can always render.
  function refresh({manual = false} = {}) {
    window.clearTimeout(pollTimer);
    pollTimer = null;
    if (activeRefresh) {
      if (manual) manualRefreshQueued = true;
      return activeRefresh.promise;
    }
    const batch = {sequence:++state.sequence, key:state.route.key, controller:new AbortController()};
    activeRefresh = batch;
    batch.promise = (async () => {
      try { await refreshData(batch); }
      finally {
        if (activeRefresh === batch) {
          activeRefresh = null;
          const delay = manualRefreshQueued ? 0 : 5000;
          manualRefreshQueued = false;
          if (!document.hidden) pollTimer = window.setTimeout(refresh, delay);
        }
      }
    })();
    return batch.promise;
  }

  async function refreshData({sequence, key, controller}) {
    const options = {signal:controller.signal};
    const [portfolio, detail] = await Promise.allSettled([api("/api/projects",options),key ? api(`/api/projects/${encodeURIComponent(key)}`,options) : Promise.resolve(null)]);
    if (sequence !== state.sequence || key !== state.route.key) return;
    if (portfolio.status === "fulfilled") {
      state.projects = portfolio.value.projects || [];
      state.projectsLoaded = true;
      renderSidebar();
    }
    if (detail.status === "fulfilled" && key) state.detail = detail.value;
    const failure = detail.status === "rejected" ? detail.reason : portfolio.status === "rejected" ? portfolio.reason : null;
    if (failure) {
      $("#refresh-status").textContent = "刷新失败 · 5 秒后重试";
      notice(`${failure.message}${state.lastSuccess ? `（上次成功刷新 ${date(state.lastSuccess,true)}）` : ""}`, true);
      if (key && !state.detail || !key && !state.projects.length && portfolio.status === "rejected") {
        renderHeading();
        replace($("#content"), empty("暂时无法读取", failure.message, '<button class="secondary" type="button" data-action="refresh">重试</button>', "!"), "content");
        $("#content").setAttribute("aria-busy", "false");
        return;
      }
    } else {
      state.lastSuccess = new Date().toISOString();
      $("#refresh-status").textContent = `已刷新 ${new Date().toLocaleTimeString("zh-CN",{hour12:false})}`;
      const warnings = state.detail?.warnings || [];
      notice(warnings.map(warning => typeof warning === "string" ? warning : JSON.stringify(warning)).join("；"));
    }
    renderContent();
    revealLinkedTask();
  }

  let pendingTask = null;
  function revealLinkedTask() {
    if (!pendingTask || state.route.view !== "features" || !state.detail) return;
    const target = document.getElementById(`task-${pendingTask}`);
    if (target) {
      target.open = true;
      target.scrollIntoView({block:"center"});
      target.querySelector("summary")?.focus({preventScroll:true});
    } else {
      notice(`关联任务 ${pendingTask} 当前不存在于此项目。历史记录中的任务关联已保留。`);
    }
    pendingTask = null;
  }

  function navigate(url, push = true) {
    if (push) history.pushState({},"",url);
    const previous = state.route;
    state.route = readRoute();
    cancelRefresh();
    pendingTask = new URLSearchParams(location.search).get("task");
    if (!previous || previous.key !== state.route.key) {
      state.detail = null;
      state.lastSuccess = null;
    }
    if (pendingTask) {
      state.open.add(detailKey("task",pendingTask));
      state.filters.set(state.route.key, {query:"",status:"all"});
    }
    const filter = filters();
    $("#task-search").value = filter.query;
    $("#status-filter").value = filter.status;
    notice();
    renderSidebar();
    renderHeading();
    if (state.route.key && !state.detail) {
      replace($("#content"), '<div class="empty-state"><div class="loading-mark" aria-hidden="true"></div><h2>正在读取项目</h2><p>载入任务与需求记录…</p></div>', "content");
      $("#content").setAttribute("aria-busy", "true");
    } else renderContent();
    if (previous) window.scrollTo({top:0});
    revealLinkedTask();
    refresh();
  }

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-nav]");
    if (link && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
      event.preventDefault();
      navigate(link.href);
      return;
    }
    const action = event.target.closest("[data-action]")?.dataset.action;
    if (action === "add") {
      $("#project-form").reset();
      $("#form-error").textContent = "";
      $("#project-dialog").showModal();
      $("#repo-root").focus();
    } else if (action === "close-dialog") $("#project-dialog").close();
    else if (action === "refresh") refresh({manual:true});
    else if (action === "clear-filter") {
      state.filters.set(state.route.key,{query:"",status:"all"});
      $("#task-search").value = "";
      $("#status-filter").value = "all";
      renderContent();
      $("#task-search").focus();
    } else if (action === "remove") {
      state.removing = state.projects.find(project => project.key === state.route.key) || state.detail?.project || {key:state.route.key};
      $("#remove-description").textContent = `将“${projectName(state.removing)}”从本地项目列表中移除。`;
      $("#remove-error").textContent = "";
      $("#remove-dialog").showModal();
    } else if (action === "cancel-remove") $("#remove-dialog").close();
  });

  // Capturing toggle handles non-bubbling native details events.
  document.addEventListener("toggle", (event) => {
    const key = event.target.dataset?.openKey;
    if (key && event.target.isConnected) {
      if (event.target.open) state.open.add(key); else state.open.delete(key);
      // The previous markup no longer describes native open state.
      delete state.signatures.content;
    }
  }, true);
  $("#task-search").addEventListener("input", event => { filters().query = event.target.value; renderContent(); });
  $("#status-filter").addEventListener("change", event => { filters().status = event.target.value; renderContent(); });
  $("#project-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const repo = $("#repo-root").value.trim(), data = $("#data-root").value.trim();
    if (!repo.startsWith("/") && !/^[A-Za-z]:[\\/]/.test(repo)) {
      $("#form-error").textContent = "请输入运行此服务的电脑上的仓库绝对路径。";
      $("#repo-root").focus(); return;
    }
    if (data && !data.startsWith("/") && !/^[A-Za-z]:[\\/]/.test(data)) {
      $("#form-error").textContent = "自定义数据目录必须为绝对路径。";
      $("#data-root").focus(); return;
    }
    const button = $("#submit-project");
    button.disabled = true; button.textContent = "正在添加…";
    $("#form-error").textContent = "";
    try {
      const result = await api("/api/projects", {method:"POST",body:JSON.stringify({repo_root:repo,...(data ? {data_root:data} : {})})});
      $("#project-dialog").close();
      if (result.project?.key) navigate(projectURL(result.project.key)); else await refresh();
    } catch (error) { $("#form-error").textContent = error.message; }
    finally { button.disabled = false; button.textContent = "添加项目"; }
  });
  $("#remove-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!state.removing) return;
    const key = state.removing.key, button = $("#submit-remove");
    button.disabled = true; button.textContent = "正在移除…";
    try {
      await api(`/api/projects/${encodeURIComponent(key)}`, {method:"DELETE"});
      ++state.sequence;
      state.projects = state.projects.filter(project => project.key !== key);
      $("#remove-dialog").close();
      state.removing = null;
      navigate("/");
    } catch (error) { $("#remove-error").textContent = error.message; }
    finally { button.disabled = false; button.textContent = "移除登记"; }
  });
  window.addEventListener("popstate", () => navigate(location.href,false));
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      window.clearTimeout(pollTimer);
      pollTimer = null;
    } else refresh();
  });
  navigate(location.href,false);
})();

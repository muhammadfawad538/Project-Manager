/* pmagent Dashboard — vanilla JS, no framework needed */

const API_BASE = '';

let currentProjectId = null;
let allProjects = [];
let currentLang = 'en';

// ── Utils ────────────────────────────────────────────────────────────────────

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function badgeClass(status, prefix) {
  const map = {
    todo: 'badge-todo', in_progress: 'badge-in_progress', in_review: 'badge-in_review',
    done: 'badge-done', blocked: 'badge-blocked', cancelled: 'badge-cancelled',
    open: 'badge-open', resolved: 'badge-resolved', closed: 'badge-closed',
    submitted: 'badge-submitted', approved: 'badge-approved', rejected: 'badge-rejected',
    pending: 'badge-pending-m', on_track: 'badge-on_track', at_risk: 'badge-at_risk',
    missed: 'badge-missed', achieved: 'badge-achieved',
    critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low',
  };
  return map[status] || 'badge-todo';
}

function statusLabel(status) {
  return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function showToast(msg, type = 'info') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}

async function api(url, opts = {}) {
  const res = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Projects ─────────────────────────────────────────────────────────────────

async function loadProjects() {
  try {
    const data = await api('/projects');
    allProjects = data.projects || [];
    renderProjectList();
    if (allProjects.length > 0 && !currentProjectId) {
      selectProject(allProjects[0].id);
    }
  } catch (err) {
    showToast('Failed to load projects: ' + err.message, 'error');
  }
}

function renderProjectList() {
  const list = $('#projectList');
  if (!allProjects.length) {
    list.innerHTML = '<div class="empty-state"><small>No projects yet</small></div>';
    return;
  }
  list.innerHTML = `
    <div class="project-list-header">Projects (${allProjects.length})</div>
    ${allProjects.map(p => `
      <button class="project-item ${p.id === currentProjectId ? 'active' : ''}" onclick="selectProject(${p.id})">
        <span class="project-item proj-name">
          <span class="status-dot status-${p.status}"></span>
          ${p.name}
        </span>
        <span class="project-item proj-meta">${p.project_type} · ${p.status}</span>
      </button>
    `).join('')}
  `;
}

async function selectProject(id) {
  currentProjectId = id;
  renderProjectList();
  $('#projectTitle').textContent = 'Loading...';
  try {
    const data = await api(`/projects/${id}`);
    renderProjectDetail(data);
  } catch (err) {
    showToast('Failed to load project: ' + err.message, 'error');
  }
}

function renderProjectDetail(p) {
  $('#projectTitle').textContent = p.name;
  $('#projectType').textContent = `${p.project_type} · ${p.industry}`;
  $('#progressRing').setAttribute('data-pct', p.progress_pct);

  const circumference = 2 * Math.PI * 20;
  const offset = circumference - (p.progress_pct / 100) * circumference;
  const fg = $('#progressRing .fg');
  fg.style.strokeDasharray = circumference;
  fg.style.strokeDashoffset = offset;

  // Stats
  $('#statTasks').textContent = `${p.done_tasks}/${p.total_tasks}`;
  $('#statIssues').textContent = p.issues.length;
  $('#statBlockers').textContent = p.blockers.length;
  $('#statCRs').textContent = p.change_requests.length;

  // Overview
  renderOverview(p);
  renderTasks(p.tasks);
  renderMilestones(p.milestones);
  renderIssues(p.issues);
  renderChangeRequests(p.change_requests);
  renderBlockers(p.blockers);
  renderDailyLogs(p.daily_logs);
  renderTeam(p.team);
}

function renderOverview(p) {
  $('#overviewStatus').innerHTML = `<span class="badge ${badgeClass(p.status)}">${statusLabel(p.status)}</span>`;
  $('#overviewObjectives').textContent = p.objectives || '—';
  $('#overviewRequirements').textContent = p.requirements || '—';
  $('#overviewCreated').textContent = p.created_at ? p.created_at.split('T')[0] : '—';
}

function renderTasks(tasks) {
  const tbody = $('#tasksTableBody');
  if (!tasks.length) { tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No tasks</td></tr>'; return; }
  tbody.innerHTML = tasks.map(t => `
    <tr>
      <td>${t.id}</td>
      <td><strong>${t.name}</strong></td>
      <td>${t.description || ''}</td>
      <td><span class="badge ${badgeClass(t.priority)}">${t.priority}</span></td>
      <td><span class="badge ${badgeClass(t.status)}">${statusLabel(t.status)}</span></td>
      <td>${t.progress_pct}%</td>
      <td>${t.assigned_to || '—'}</td>
    </tr>
  `).join('');
}

function renderMilestones(milestones) {
  const tbody = $('#milestonesTableBody');
  if (!milestones.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No milestones</td></tr>'; return; }
  tbody.innerHTML = milestones.map(m => `
    <tr>
      <td>${m.id}</td>
      <td><strong>${m.name}</strong></td>
      <td>${m.description || ''}</td>
      <td><span class="badge ${badgeClass(m.status)}">${statusLabel(m.status)}</span></td>
    </tr>
  `).join('');
}

function renderIssues(issues) {
  const tbody = $('#issuesTableBody');
  if (!issues.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No issues</td></tr>'; return; }
  tbody.innerHTML = issues.map(i => `
    <tr>
      <td>${i.id}</td>
      <td><strong>${i.title}</strong></td>
      <td><span class="badge ${badgeClass(i.priority)}">${i.priority}</span></td>
      <td><span class="badge ${badgeClass(i.status)}">${statusLabel(i.status)}</span></td>
      <td>${i.assigned_to || '—'}</td>
    </tr>
  `).join('');
}

function renderChangeRequests(crs) {
  const tbody = $('#crsTableBody');
  if (!crs.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No change requests</td></tr>'; return; }
  tbody.innerHTML = crs.map(cr => `
    <tr>
      <td>${cr.id}</td>
      <td><strong>${cr.title}</strong></td>
      <td>${cr.justification || '—'}</td>
      <td><span class="badge ${badgeClass(cr.status)}">${statusLabel(cr.status)}</span></td>
      <td>${cr.impact_scope || '—'}</td>
    </tr>
  `).join('');
}

function renderBlockers(blockers) {
  const tbody = $('#blockersTableBody');
  if (!blockers.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><h3>No blockers — all clear!</h3></td></tr>'; return; }
  tbody.innerHTML = blockers.map(b => `
    <tr>
      <td>${b.id}</td>
      <td><strong>${b.name}</strong></td>
      <td><span class="badge ${badgeClass(b.status)}">${b.status}</span></td>
      <td>${b.assigned_to || '—'}</td>
      <td>${b.due_date || '—'}</td>
    </tr>
  `).join('');
}

function renderDailyLogs(logs) {
  const tbody = $('#logsTableBody');
  if (!logs.length) { tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No daily logs yet</td></tr>'; return; }
  tbody.innerHTML = logs.map(l => `
    <tr>
      <td>${l.id}</td>
      <td>Task #${l.task_id}</td>
      <td>${l.team_member || '—'}</td>
      <td>${(l.yesterday_progress || '').slice(0, 60) || '—'}</td>
      <td>${l.hours_logged}h</td>
      <td>${l.log_date ? l.log_date.split('T')[0] : ''}</td>
    </tr>
  `).join('');
}

function renderTeam(team) {
  const tbody = $('#teamTableBody');
  if (!team.length) { tbody.innerHTML = '<tr><td colspan="3" class="empty-state">No team members</td></tr>'; return; }
  tbody.innerHTML = team.map(m => `
    <tr>
      <td>${m.id}</td>
      <td><strong>${m.name}</strong></td>
      <td><span class="badge badge-medium">${m.role}</span></td>
    </tr>
  `).join('');
}

// ── Forms ────────────────────────────────────────────────────────────────────

async function submitIssue(e) {
  e.preventDefault();
  const data = {
    title: $('#issueTitle').value,
    description: $('#issueDesc').value,
    priority: $('#issuePriority').value,
  };
  try {
    await api(`/projects/${currentProjectId}/issues`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    showToast('Issue created', 'success');
    e.target.reset();
    loadProjects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function submitCR(e) {
  e.preventDefault();
  const data = {
    title: $('#crTitle').value,
    justification: $('#crJustification').value,
    impact_scope: $('#crImpact').value,
  };
  try {
    await api(`/projects/${currentProjectId}/change-requests`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    showToast('Change request submitted', 'success');
    e.target.reset();
    loadProjects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function submitDailyLog(e) {
  e.preventDefault();
  const data = {
    task_id: parseInt($('#logTaskId').value),
    team_member_id: parseInt($('#logMemberId').value),
    yesterday_progress: $('#logYesterday').value,
    today_plan: $('#logToday').value,
    blockers: $('#logBlockers').value,
    hours_logged: parseFloat($('#logHours').value) || 0,
  };
  try {
    await api(`/projects/${currentProjectId}/daily-logs`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
    showToast('Daily log saved', 'success');
    e.target.reset();
    loadProjects();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

function switchTab(tabName) {
  $$('.tab').forEach(t => t.classList.remove('active'));
  $$('.tab-panel').forEach(p => p.classList.remove('active'));
  event.target.classList.add('active');
  $(`#panel-${tabName}`).classList.add('active');
}

// ── Language toggle ──────────────────────────────────────────────────────────

const I18N = {
  en: {
    langBtn: 'عربي',
    projectDetails: 'Project Details',
    projectListHeader: 'Projects',
    sidebarFooter: 'pmagent v0.1 · GCC Markets',
    selectProject: 'Select a project',
    overview: 'Overview',
    tasks: 'Tasks',
    milestones: 'Milestones',
    issues: 'Issues',
    crs: 'Change Requests',
    blockers: 'Blockers',
    logs: 'Daily Logs',
    team: 'Team',
    progress: 'Progress',
    openIssues: 'Open Issues',
    blockersStat: 'Blockers',
    changeRequests: 'Change Requests',
    status: 'Status',
    created: 'Created',
    objectives: 'Objectives',
    requirements: 'Requirements',
    allTasks: 'All Tasks',
    name: 'Name',
    description: 'Description',
    priority: 'Priority',
    status_: 'Status',
    progress_: 'Progress',
    assignee: 'Assignee',
    noProjects: 'No projects yet',
    noTasks: 'No tasks',
    noMilestones: 'No milestones',
    reportIssue: 'Report New Issue',
    title_: 'Title',
    priority_: 'Priority',
    description_: 'Description',
    createIssue: 'Create Issue',
    submitCR: 'Submit Change Request',
    impactScope: 'Impact Scope',
    justification: 'Justification',
    submitCRBtn: 'Submit CR',
    blockedOverdue: 'Blocked & Overdue Tasks',
    dueDate: 'Due Date',
    logStandup: 'Log Daily Standup',
    taskId: 'Task ID',
    memberId: 'Team Member ID',
    hoursLogged: 'Hours Logged',
    yesterday: "Yesterday's Progress",
    todayPlan: "Today's Plan",
    blockers_: 'Blockers',
    saveLog: 'Save Daily Log',
    recentStandups: 'Recent Standups',
    member: 'Member',
    date: 'Date',
    teamMembers: 'Team Members',
    role: 'Role',
    selectProjectView: 'Select a project to view tasks',
    selectProject_: 'Select a project',
    noBlockers: 'No blockers — all clear!',
    noLogs: 'No daily logs yet',
    noIssues: 'No issues',
    noCRs: 'No change requests',
    noTeam: 'No team members',
    eG: 'e.g.',
    loginTimeout: 'e.g. Login timeout',
    ssoAuth: 'e.g. Add SSO authentication',
    whyChange: 'Why is this change needed?',
    whatCompleted: 'What was completed...',
    whatToday: 'What will be done today...',
    anyImpediments: 'Any impediments?',
    schedule: 'Schedule',
    scope: 'Scope',
    budget: 'Budget',
    quality: 'Quality',
    low: 'Low',
    medium: 'Medium',
    high: 'High',
    critical: 'Critical',
  },
  ar: {
    langBtn: 'English',
    projectDetails: 'تفاصيل المشروع',
    projectListHeader: 'المشاريع',
    sidebarFooter: 'pmagent v0.1 · أسواق الخليج',
    selectProject: 'اختر مشروعاً',
    overview: 'نظرة عامة',
    tasks: 'المهام',
    milestones: 'المراحل',
    issues: 'المشاكل',
    crs: 'طلبات التغيير',
    blockers: 'العوائق',
    logs: 'السجلات اليومية',
    team: 'الفريق',
    progress: 'التقدم',
    openIssues: 'المشاكل المفتوحة',
    blockersStat: 'العوائق',
    changeRequests: 'طلبات التغيير',
    status: 'الحالة',
    created: 'تاريخ الإنشاء',
    objectives: 'الأهداف',
    requirements: 'المتطلبات',
    allTasks: 'جميع المهام',
    name: 'الاسم',
    description: 'الوصف',
    priority: 'الأولوية',
    status_: 'الحالة',
    progress_: 'التقدم',
    assignee: 'المسند',
    noProjects: 'لا توجد مشاريع',
    noTasks: 'لا توجد مهام',
    noMilestones: 'لا توجد مراحل',
    reportIssue: 'الإبلاغ عن مشكلة',
    title_: 'العنوان',
    priority_: 'الأولوية',
    description_: 'الوصف',
    createIssue: 'إنشاء مشكلة',
    submitCR: 'طلب تغيير',
    impactScope: 'نطاق التأثير',
    justification: 'التبرير',
    submitCRBtn: 'إرسال',
    blockedOverdue: 'المهام المتوقفة والمتأخرة',
    dueDate: 'تاريخ الاستحقاق',
    logStandup: 'تسجيل اجتماع يومي',
    taskId: 'رقم المهمة',
    memberId: 'رقم عضو الفريق',
    hoursLogged: 'ساعات مسجلة',
    yesterday: 'تقدم الأمس',
    todayPlan: 'خطة اليوم',
    blockers_: 'العوائق',
    saveLog: 'حفظ السجل',
    recentStandups: 'الاجتماعات الأخيرة',
    member: 'العضو',
    date: 'التاريخ',
    teamMembers: 'أعضاء الفريق',
    role: 'الدور',
    selectProjectView: 'اختر مشروعاً لعرض المهام',
    selectProject_: 'اختر مشروعاً',
    noBlockers: 'لا توجد عوائق — كل شيء سليم!',
    noLogs: 'لا توجد سجلات يومية',
    noIssues: 'لا توجد مشاكل',
    noCRs: 'لا توجد طلبات تغيير',
    noTeam: 'لا يوجد أعضاء فريق',
    eG: 'مثال:',
    loginTimeout: 'مثال: انتهاء مهلة تسجيل الدخول',
    ssoAuth: 'مثال: إضافة مصادقة SSO',
    whyChange: 'لماذا هذا التغيير مطلوب؟',
    whatCompleted: 'ما الذي تم إنجازه...',
    whatToday: 'ما الذي سيتم إنجازه اليوم...',
    anyImpediments: 'هل هناك عوائق؟',
    schedule: 'الجدول الزمني',
    scope: 'النطاق',
    budget: 'الميزانية',
    quality: 'الجودة',
    low: 'منخفض',
    medium: 'متوسط',
    high: 'مرتفع',
    critical: 'حرج',
  },
};

function t(key) {
  const dict = I18N[currentLang] || I18N.en;
  return dict[key] || key;
}

function toggleLang() {
  currentLang = currentLang === 'en' ? 'ar' : 'en';
  document.body.classList.toggle('rtl', currentLang === 'ar');
  document.documentElement.lang = currentLang;
  $('#langBtn').textContent = t('langBtn');

  // Tab labels
  const tabs = ['overview', 'tasks', 'milestones', 'issues', 'crs', 'blockers', 'logs', 'team'];
  tabs.forEach(name => {
    const tab = document.querySelector(`.tab[data-tab="${name}"]`);
    if (tab) tab.textContent = t(name);
  });

  // Stat labels
  $('#statTasks').previousElementSibling.textContent = t('progress');
  $('#statIssues').previousElementSibling.textContent = t('openIssues');
  $('#statBlockers').previousElementSibling.textContent = t('blockersStat');
  $('#statCRs').previousElementSibling.textContent = t('changeRequests');

  // Overview card
  const cardTitles = document.querySelectorAll('.card-title');
  cardTitles.forEach(el => {
    const text = el.textContent.trim().toLowerCase();
    if (text.includes('project details')) el.textContent = t('projectDetails') || 'Project Details';
    if (text.includes('all tasks')) el.textContent = t('allTasks');
    if (text.includes('milestones')) el.textContent = t('milestones');
    if (text.includes('report new issue')) el.textContent = t('reportIssue');
    if (text.includes('issues') && !text.includes('report')) el.textContent = t('issues');
    if (text.includes('submit change request')) el.textContent = t('submitCR');
    if (text.includes('change requests') && !text.includes('submit')) el.textContent = t('crs');
    if (text.includes('blocked')) el.textContent = t('blockedOverdue');
    if (text.includes('log daily')) el.textContent = t('logStandup');
    if (text.includes('recent')) el.textContent = t('recentStandups');
    if (text.includes('team members')) el.textContent = t('teamMembers');
  });

  // Form labels and placeholders
  const labels = document.querySelectorAll('label');
  labels.forEach(el => {
    const text = el.textContent.trim().toLowerCase();
    if (text.includes('task id')) el.textContent = t('taskId');
    else if (text.includes('team member')) el.textContent = t('memberId');
    else if (text.includes('hours logged')) el.textContent = t('hoursLogged');
    else if (text.includes('yesterday')) el.textContent = t('yesterday');
    else if (text.includes('today')) el.textContent = t('todayPlan');
    else if (text.includes('blockers') && !text.includes('any')) el.textContent = t('blockers_');
    else if (text.includes('title') && !text.includes('impact')) el.textContent = t('title_');
    else if (text.includes('priority')) el.textContent = t('priority_');
    else if (text.includes('description') && !text.includes('impact')) el.textContent = t('description_');
    else if (text.includes('impact scope')) el.textContent = t('impactScope');
    else if (text.includes('justification')) el.textContent = t('justification');
  });

  const placeholders = document.querySelectorAll('textarea, input[placeholder]');
  placeholders.forEach(el => {
    const ph = el.placeholder.toLowerCase();
    if (ph.includes('login')) el.placeholder = t('loginTimeout');
    else if (ph.includes('sso') || ph.includes('add')) el.placeholder = t('ssoAuth');
    else if (ph.includes('why')) el.placeholder = t('whyChange');
    else if (ph.includes('what was completed') || ph.includes('completed')) el.placeholder = t('whatCompleted');
    else if (ph.includes('what will be done') || ph.includes('today')) el.placeholder = t('whatToday');
    else if (ph.includes('impediments') || ph.includes('any blockers')) el.placeholder = t('anyImpediments');
  });

  // Form buttons
  const buttons = document.querySelectorAll('button[type="submit"]');
  buttons.forEach(btn => {
    const text = btn.textContent.trim().toLowerCase();
    if (text.includes('create issue')) btn.textContent = t('createIssue');
    else if (text.includes('submit cr')) btn.textContent = t('submitCRBtn');
    else if (text.includes('save daily')) btn.textContent = t('saveLog');
  });

  // Select options
  const selects = document.querySelectorAll('select');
  selects.forEach(sel => {
    Array.from(sel.options).forEach(opt => {
      const val = opt.value.toLowerCase();
      const text = opt.textContent.trim().toLowerCase();
      if (text === 'low' || val === 'low') opt.textContent = t('low');
      else if (text === 'medium' || val === 'medium') opt.textContent = t('medium');
      else if (text === 'high' || val === 'high') opt.textContent = t('high');
      else if (text === 'critical' || val === 'critical') opt.textContent = t('critical');
      else if (text === 'schedule' || val === 'schedule') opt.textContent = t('schedule');
      else if (text === 'scope' || val === 'scope') opt.textContent = t('scope');
      else if (text === 'budget' || val === 'budget') opt.textContent = t('budget');
      else if (text === 'quality' || val === 'quality') opt.textContent = t('quality');
    });
  });

  // Re-render dynamic content
  if (currentProjectId) selectProject(currentProjectId);
  else renderProjectList();
}

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadProjects();

  $('#issueForm').addEventListener('submit', submitIssue);
  $('#crForm').addEventListener('submit', submitCR);
  $('#logForm').addEventListener('submit', submitDailyLog);

  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  $('#langBtn').addEventListener('click', toggleLang);

  // Auto-refresh every 30 seconds
  setInterval(() => { if (currentProjectId) loadProjects(); }, 30000);
});

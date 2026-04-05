(() => {
  const ROUTES = {
    admin: [
      { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
      { key: 'users', label: 'Users', icon: 'bi-people' },
      { key: 'bins', label: 'Bins', icon: 'bi-trash3' },
      { key: 'tasks', label: 'Tasks', icon: 'bi-list-task' },
      { key: 'alerts', label: 'Alerts', icon: 'bi-bell' },
      { key: 'reports', label: 'Reports', icon: 'bi-bar-chart' },
      { key: 'validations', label: 'AI Validation', icon: 'bi-cpu' }
    ],
    city_head: [
      { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
      { key: 'bins', label: 'Bins', icon: 'bi-trash3' },
      { key: 'tasks', label: 'Tasks', icon: 'bi-list-task' },
      { key: 'alerts', label: 'Alerts', icon: 'bi-bell' },
      { key: 'reports', label: 'Reports', icon: 'bi-bar-chart' },
      { key: 'validations', label: 'AI Validation', icon: 'bi-cpu' }
    ],
    staff: [
      { key: 'dashboard', label: 'Dashboard', icon: 'bi-speedometer2' },
      { key: 'tasks', label: 'My Tasks', icon: 'bi-list-task' },
      { key: 'bins', label: 'My Bins', icon: 'bi-trash3' },
      { key: 'alerts', label: 'Alerts', icon: 'bi-bell' },
      { key: 'profile', label: 'Profile', icon: 'bi-person-circle' }
    ]
  };

  const state = {
    selectedRole: 'admin',
    user: null,
    route: null,
    lookups: null,
    pageData: null,
    sensorTimer: null,
    charts: [],
    dataTables: [],
    reportDateFilter: { from: '', to: '' },
    validationResult: null
  };

  const el = {
    splash: document.getElementById('splash-screen'),
    loginView: document.getElementById('login-view'),
    dashboardView: document.getElementById('dashboard-view'),
    roleSelector: document.getElementById('role-selector'),
    loginForm: document.getElementById('login-form'),
    loginError: document.getElementById('login-error'),
    pageTitle: document.getElementById('page-title'),
    topbarDate: document.getElementById('topbar-date'),
    topbarTime: document.getElementById('topbar-time'),
    sidebarNav: document.getElementById('sidebar-nav'),
    sidebarUserName: document.getElementById('sidebar-user-name'),
    sidebarUserRole: document.getElementById('sidebar-user-role'),
    sidebarUserMeta: document.getElementById('sidebar-user-meta'),
    contentArea: document.getElementById('content-area'),
    logoutBtn: document.getElementById('logout-btn'),
    toast: document.getElementById('app-toast'),
    toastBody: document.getElementById('app-toast-body')
  };

  const toast = new bootstrap.Toast(el.toast, { delay: 2600 });
  const chart3dPlugin = {
    id: 'smartWaste3d',
    beforeDatasetsDraw(chart, _args, options = {}) {
      if (!options.enabled) return;

      const { ctx } = chart;
      const depth = Number(options.depth || 10);

      chart.data.datasets.forEach((dataset, datasetIndex) => {
        const meta = chart.getDatasetMeta(datasetIndex);
        if (!meta || meta.hidden) return;

        if (meta.type === 'bar') {
          meta.data.forEach((bar, pointIndex) => {
            const properties = bar.getProps(['x', 'y', 'base', 'width'], true);
            const left = properties.x - properties.width / 2;
            const right = properties.x + properties.width / 2;
            const top = Math.min(properties.y, properties.base);
            const bottom = Math.max(properties.y, properties.base);
            const frontColor = paletteColor(dataset.backgroundColor, pointIndex, 'rgba(46, 125, 50, 0.82)');

            ctx.save();
            ctx.fillStyle = shiftColor(frontColor, -34, 0.95);
            ctx.beginPath();
            ctx.moveTo(right, top);
            ctx.lineTo(right + depth, top - depth * 0.55);
            ctx.lineTo(right + depth, bottom - depth * 0.55);
            ctx.lineTo(right, bottom);
            ctx.closePath();
            ctx.fill();

            ctx.fillStyle = shiftColor(frontColor, 18, 0.98);
            ctx.beginPath();
            ctx.moveTo(left, top);
            ctx.lineTo(right, top);
            ctx.lineTo(right + depth, top - depth * 0.55);
            ctx.lineTo(left + depth, top - depth * 0.55);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          });
        }

        if (meta.type === 'doughnut' || meta.type === 'pie') {
          meta.data.forEach((arc, pointIndex) => {
            const properties = arc.getProps(['x', 'y', 'innerRadius', 'outerRadius', 'startAngle', 'endAngle'], true);
            const frontColor = paletteColor(dataset.backgroundColor, pointIndex, 'rgba(46, 125, 50, 0.82)');

            ctx.save();
            ctx.fillStyle = shiftColor(frontColor, -28, 0.92);
            ctx.beginPath();
            ctx.arc(properties.x, properties.y + depth * 0.72, properties.outerRadius, properties.startAngle, properties.endAngle);
            ctx.arc(properties.x, properties.y + depth * 0.72, properties.innerRadius, properties.endAngle, properties.startAngle, true);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          });
        }
      });
    }
  };

  if (typeof Chart !== 'undefined') {
    Chart.register(chart3dPlugin);
  }

  function init() {
    renderRoleButtons();
    bindEvents();
    updateClock();
    setInterval(updateClock, 1000);
    setTimeout(async () => {
      el.splash.classList.add('hidden');
      el.loginView.classList.remove('d-none');
      await restoreSession();
    }, 800);
  }

  function bindEvents() {
    el.loginForm.addEventListener('submit', handleLogin);
    el.logoutBtn.addEventListener('click', logout);
  }

  function renderRoleButtons() {
    const roles = [
      { id: 'admin', label: 'Admin', icon: 'bi-shield-check' },
      { id: 'city_head', label: 'City Head', icon: 'bi-buildings' },
      { id: 'staff', label: 'Staff', icon: 'bi-person-badge' }
    ];

    el.roleSelector.innerHTML = roles.map(role => `
      <button type="button" class="btn ${role.id === state.selectedRole ? 'btn-success' : 'btn-outline-success'} role-btn rounded-pill px-4" data-role="${role.id}">
        <i class="bi ${role.icon} me-2"></i>${role.label}
      </button>
    `).join('');

    el.roleSelector.querySelectorAll('[data-role]').forEach(button => {
      button.addEventListener('click', () => {
        state.selectedRole = button.dataset.role;
        renderRoleButtons();
      });
    });
  }

  async function api(path, options = {}) {
    const config = { credentials: 'same-origin', ...options };
    if (config.body && !(config.body instanceof FormData) && !config.headers?.['Content-Type']) {
      config.headers = { ...(config.headers || {}), 'Content-Type': 'application/json' };
      config.body = JSON.stringify(config.body);
    }

    let response;
    try {
      response = await fetch(path, config);
    } catch (_error) {
      throw new Error('Unable to reach the server. Make sure python app.py is running, then try again.');
    }

    const contentType = response.headers.get('content-type') || '';
    let payload = null;
    try {
      payload = contentType.includes('application/json') ? await response.json() : await response.text();
    } catch (_error) {
      payload = null;
    }

    if (!response.ok) {
      let message = typeof payload === 'string' ? payload : payload?.error || payload?.message || '';
      if (!message || /^<!doctype html/i.test(message) || /^<html/i.test(message)) {
        if (response.status === 401) message = 'Your session has expired. Please log in again.';
        else if (response.status === 403) message = 'You do not have permission to perform this action.';
        else if (response.status === 404) message = 'The requested record could not be found.';
        else if (response.status === 413) message = 'Uploaded file is too large. Please choose a smaller image.';
        else if (response.status >= 500) message = 'The server hit an unexpected error. Please try again.';
        else message = 'The request could not be completed.';
      }
      throw new Error(message);
    }

    return payload;
  }

  async function restoreSession() {
    try {
      const payload = await api('/api/auth/me');
      if (!payload.user) return;
      state.user = payload.user;
      state.selectedRole = payload.user.role;
      state.route = ROUTES[payload.user.role][0].key;
      await refreshLookups();
      el.loginView.classList.add('d-none');
      el.dashboardView.classList.remove('d-none');
      await renderShell();
    } catch (error) {
      showToast(error.message, 'danger');
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    const username = event.target.username.value.trim();
    const password = event.target.password.value.trim();

    if (!username || !password) {
      showLoginError('Please enter both username and password.');
      return;
    }

    try {
      const payload = await api('/api/auth/login', {
        method: 'POST',
        body: { username, password, role: state.selectedRole }
      });
      state.user = payload.user;
      state.route = ROUTES[state.user.role][0].key;
      await refreshLookups();
      event.target.reset();
      el.loginError.classList.add('d-none');
      el.loginView.classList.add('d-none');
      el.dashboardView.classList.remove('d-none');
      await renderShell();
      showToast(`Welcome ${state.user.fullName}`);
    } catch (error) {
      showLoginError(error.message);
    }
  }

  async function logout() {
    destroyCharts();
    destroyDataTables();
    stopSensorPolling();
    await api('/api/auth/logout', { method: 'POST' });
    state.user = null;
    state.route = null;
    state.lookups = null;
    state.pageData = null;
    state.reportDateFilter = { from: '', to: '' };
    state.validationResult = null;
    el.dashboardView.classList.add('d-none');
    el.loginView.classList.remove('d-none');
    showToast('Session cleared');
  }

  function showLoginError(message) {
    el.loginError.textContent = message;
    el.loginError.classList.remove('d-none');
  }

  function showToast(message, tone = 'success') {
    el.toast.className = `toast align-items-center text-bg-${tone} border-0`;
    el.toastBody.textContent = message;
    toast.show();
  }

  function updateClock() {
    const now = new Date();
    el.topbarDate.textContent = now.toLocaleDateString(undefined, {
      weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
    });
    el.topbarTime.textContent = now.toLocaleTimeString(undefined, {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
  }

  async function refreshLookups() {
    if (!state.user) return;
    state.lookups = await api('/api/lookups');
  }

  async function renderShell() {
    if (!state.user) return;

    el.sidebarUserName.textContent = state.user.fullName;
    el.sidebarUserRole.textContent = titleCase(state.user.role.replace('_', ' '));
    el.sidebarUserMeta.textContent = `${state.user.city || 'Smart City'} | ${state.user.zone || 'N/A'} | ${state.user.meta || 'SQLite-backed account'}`;

    el.sidebarNav.innerHTML = ROUTES[state.user.role].map(item => `
      <a href="#" class="nav-link ${item.key === state.route ? 'active' : ''}" data-route="${item.key}">
        <i class="bi ${item.icon} me-2"></i>${item.label}
      </a>
    `).join('');

    el.sidebarNav.querySelectorAll('[data-route]').forEach(link => {
      link.addEventListener('click', async event => {
        event.preventDefault();
        state.route = link.dataset.route;
        await renderShell();
      });
    });

    await renderPage();
  }

  async function renderPage() {
    destroyCharts();
    destroyDataTables();
    stopSensorPolling();
    el.contentArea.innerHTML = `<div class="content-card"><div class="text-muted">Loading ${state.route}...</div></div>`;
    try {
      state.pageData = await loadPageData(state.route);
      el.pageTitle.textContent = pageTitle(state.route);
      el.contentArea.innerHTML = renderPageHtml(state.route, state.pageData);
      await mountPage(state.route, state.pageData);
      const dataTables = initializeDataTables();
      mountPageEnhancements(state.route, state.pageData, dataTables);
    } catch (error) {
      el.contentArea.innerHTML = `
        <div class="content-card">
          <div class="alert alert-danger mb-0">
            <strong>Unable to load this page.</strong><br>
            ${escapeHtml(error.message)}
          </div>
        </div>
      `;
      showToast(error.message, 'danger');
    }
  }

  async function loadPageData(route) {
    switch (route) {
      case 'dashboard': return api('/api/dashboard');
      case 'users': return api('/api/users');
      case 'bins': return api('/api/bins');
      case 'tasks': return api('/api/tasks');
      case 'alerts': return api('/api/alerts');
      case 'reports': return api('/api/reports');
      case 'validations': return api('/api/validations');
      case 'profile': return (await api('/api/auth/me')).user;
      default: return {};
    }
  }

  function pageTitle(route) {
    return {
      dashboard: 'Dashboard',
      users: 'User Management',
      bins: 'Bin Management',
      tasks: 'Task Management',
      alerts: 'Alerts',
      reports: 'Reports',
      validations: 'AI Validation',
      profile: 'Profile'
    }[route] || 'Dashboard';
  }

  function renderPageHtml(route, data) {
    switch (route) {
      case 'dashboard': return renderDashboard(data);
      case 'users': return renderUsersPage(data);
      case 'bins': return renderBinsPage(data);
      case 'tasks': return renderTasksPage(data);
      case 'alerts': return renderAlertsPage(data);
      case 'reports': return renderReportsPage(data);
      case 'validations': return renderValidationsPage(data);
      case 'profile': return renderProfilePage(data);
      default: return `<div class="content-card">Unknown page</div>`;
    }
  }

  function destroyCharts() {
    state.charts.forEach(chart => chart.destroy());
    state.charts = [];
  }

  function destroyDataTables() {
    state.dataTables.forEach(table => {
      try {
        table.destroy();
      } catch (_error) {
        // Ignore teardown issues when the DOM has already been replaced.
      }
    });
    state.dataTables = [];
  }

  function mountChart(id, type, labels, values, label, options = {}) {
    const canvas = document.getElementById(id);
    if (!canvas || typeof Chart === 'undefined') return;

    const palette = buildChartPalette(options.palette || (type === 'doughnut' || type === 'pie' ? 'copper' : 'forest'));
    const backgroundColors = labels.map((_, index) => palette[index % palette.length].background);
    const borderColors = labels.map((_, index) => palette[index % palette.length].border);
    const datasetBackground = type === 'line'
      ? shiftColor(backgroundColors[0], 4, 0.18)
      : (type === 'doughnut' || type === 'pie' ? backgroundColors : backgroundColors);
    const datasetBorder = type === 'line' ? borderColors[0] : borderColors;

    const chart = new Chart(canvas, {
      type,
      data: {
        labels,
        datasets: [{
          label,
          data: values,
          borderWidth: 2,
          tension: 0.35,
          borderRadius: 10,
          fill: type === 'line',
          hoverOffset: type === 'doughnut' || type === 'pie' ? 8 : 0,
          backgroundColor: options.backgroundColor || datasetBackground,
          borderColor: options.borderColor || datasetBorder
        }]
      },
      options: {
        maintainAspectRatio: false,
        layout: { padding: { top: 18, right: 20, bottom: 10, left: 8 } },
        plugins: {
          legend: {
            display: !!options.showLegend,
            position: options.legendPosition || 'bottom',
            labels: {
              usePointStyle: true,
              padding: 18,
              boxWidth: 10,
              color: '#355640'
            }
          },
          tooltip: {
            backgroundColor: 'rgba(17, 24, 39, 0.9)',
            padding: 12,
            displayColors: true
          },
          smartWaste3d: {
            enabled: options.threeDimensional !== false,
            depth: options.depth || 12
          }
        },
        cutout: options.cutout || undefined,
        scales: type === 'doughnut' || type === 'pie' ? {} : {
          x: {
            grid: { display: false },
            ticks: { color: '#55705e' }
          },
          y: {
            beginAtZero: true,
            max: options.max || undefined,
            ticks: { precision: 0, color: '#55705e' },
            grid: { color: 'rgba(46, 125, 50, 0.10)' }
          }
        }
      }
    });
    state.charts.push(chart);
  }

  function buildChartPalette(name) {
    const palettes = {
      forest: [
        { background: 'rgba(46, 125, 50, 0.86)', border: '#1b5e20' },
        { background: 'rgba(67, 160, 71, 0.86)', border: '#2e7d32' },
        { background: 'rgba(129, 199, 132, 0.92)', border: '#558b2f' },
        { background: 'rgba(27, 94, 32, 0.88)', border: '#123d16' }
      ],
      copper: [
        { background: 'rgba(255, 167, 38, 0.92)', border: '#c77800' },
        { background: 'rgba(255, 112, 67, 0.90)', border: '#c63f17' },
        { background: 'rgba(255, 202, 40, 0.92)', border: '#d39b00' },
        { background: 'rgba(141, 110, 99, 0.88)', border: '#6d4c41' }
      ],
      lagoon: [
        { background: 'rgba(13, 110, 253, 0.88)', border: '#0a58ca' },
        { background: 'rgba(32, 201, 151, 0.86)', border: '#0f8f6b' },
        { background: 'rgba(25, 135, 84, 0.86)', border: '#146c43' },
        { background: 'rgba(111, 66, 193, 0.86)', border: '#5a32a3' }
      ]
    };

    return palettes[name] || palettes.forest;
  }

  function paletteColor(value, index, fallback) {
    if (Array.isArray(value)) return value[index % value.length] || fallback;
    return value || fallback;
  }

  function shiftColor(value, amount, alphaOverride = null) {
    const color = parseColor(value);
    if (!color) return value;

    const clamp = component => Math.max(0, Math.min(255, component));
    const alpha = alphaOverride ?? color.alpha;
    return `rgba(${clamp(color.red + amount)}, ${clamp(color.green + amount)}, ${clamp(color.blue + amount)}, ${alpha})`;
  }

  function parseColor(value) {
    if (!value) return null;
    const input = String(value).trim();

    if (input.startsWith('#')) {
      const hex = input.slice(1);
      const size = hex.length === 3 ? 1 : 2;
      const expand = token => size === 1 ? `${token}${token}` : token;
      const [red, green, blue] = [0, size, size * 2].map(offset => parseInt(expand(hex.slice(offset, offset + size)), 16));
      if ([red, green, blue].some(Number.isNaN)) return null;
      return { red, green, blue, alpha: 1 };
    }

    const match = input.match(/^rgba?\(([^)]+)\)$/i);
    if (!match) return null;
    const parts = match[1].split(',').map(part => part.trim());
    const [red, green, blue] = parts.slice(0, 3).map(Number);
    const alpha = parts[3] === undefined ? 1 : Number(parts[3]);
    if ([red, green, blue, alpha].some(Number.isNaN)) return null;
    return { red, green, blue, alpha };
  }

  function renderPageHero(title, subtitle) {
    return `
      <div class="page-hero">
        <h4 class="fw-bold">${escapeHtml(title)}</h4>
        <div class="text-muted">${escapeHtml(subtitle)}</div>
      </div>
    `;
  }

  function renderInlineFeedback(id) {
    return `<div id="${id}" class="alert inline-feedback mb-3"></div>`;
  }

  function setInlineFeedback(id, message, tone = 'danger') {
    const element = document.getElementById(id);
    if (!element) return;
    element.className = `alert inline-feedback show alert-${tone} mb-3`;
    element.textContent = message;
  }

  function clearInlineFeedback(id) {
    const element = document.getElementById(id);
    if (!element) return;
    element.className = 'alert inline-feedback mb-3';
    element.textContent = '';
  }

  function showActionError(feedbackId, error, fallbackMessage) {
    const message = error instanceof Error && error.message ? error.message : fallbackMessage;
    setInlineFeedback(feedbackId, message, 'danger');
    showToast(message, 'danger');
  }

  function showActionSuccess(feedbackId, message) {
    setInlineFeedback(feedbackId, message, 'success');
    showToast(message);
  }

  function showActionInfo(feedbackId, message) {
    setInlineFeedback(feedbackId, message, 'info');
  }

  function renderMetricCards(metrics) {
    return `
      <div class="section-grid metrics-4">
        ${metrics.map(metric => `
          <div class="metric-card">
            <div class="metric-label">${escapeHtml(metric.label)}</div>
            <div class="metric-value">${escapeHtml(metric.value)}</div>
            <div class="metric-subtext">${escapeHtml(metric.subtext)}</div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderStatusBadge(value) {
    const token = String(value || 'unknown').toLowerCase();
    let cls = 'status-muted';
    if (['active', 'generated', 'completed', 'match', 'resolved', 'reviewed'].includes(token)) cls = 'status-success';
    else if (['pending', 'medium', 'in_progress', 'draft', 'new'].includes(token)) cls = 'status-warning';
    else if (['high', 'overdue', 'inactive', 'mismatch', 'maintenance'].includes(token)) cls = 'status-danger';
    else if (['low', 'open', 'read', 'unknown'].includes(token)) cls = 'status-info';
    return `<span class="status-badge ${cls}">${escapeHtml(value || 'unknown')}</span>`;
  }

  function renderDashboard(data) {
    const taskStatusCounts = summarizeByKey(data.recentTasks || [], 'status');
    const validationCounts = summarizeByKey(data.recentValidations || [], 'match');

    return `
      <div class="section-grid">
        ${renderPageHero('Operations Snapshot', 'The previous richer dashboard style is back, now powered by live SQLite data.')}
        ${renderMetricCards(data.metrics || [])}

        <div class="section-grid two-col">
          <div class="chart-card">
            <div class="card-title-row"><div><h5>Task Status Overview</h5><div class="text-muted small">Open work across the most recent tasks</div></div><span class="kpi-chip">${(data.recentTasks || []).length} recent tasks</span></div>
            <div class="chart-wrap"><canvas id="dashboard-task-chart"></canvas></div>
            <div class="row g-3 mt-1">
              ${Object.entries(taskStatusCounts).map(([label, value]) => `<div class="col-md-4"><div class="soft-stat"><div class="soft-stat-label">${escapeHtml(label)}</div><div class="soft-stat-value">${escapeHtml(value)}</div></div></div>`).join('')}
            </div>
          </div>
          <div class="chart-card">
            <div class="card-title-row"><div><h5>Validation Results</h5><div class="text-muted small">Recent AI versus sensor comparison outcomes</div></div><span class="kpi-chip">${(data.recentValidations || []).length} recent validations</span></div>
            <div class="chart-wrap"><canvas id="dashboard-validation-chart"></canvas></div>
            <div class="row g-3 mt-1">
              ${Object.entries(validationCounts).map(([label, value]) => `<div class="col-md-4"><div class="soft-stat"><div class="soft-stat-label">${escapeHtml(label)}</div><div class="soft-stat-value">${escapeHtml(value)}</div></div></div>`).join('')}
            </div>
          </div>
        </div>

        <div class="section-grid two-col">
          <div class="content-card">
            <div class="card-title-row"><div><h5>Recent Tasks</h5><div class="text-muted small">Latest work orders from SQLite</div></div></div>
            ${renderSimpleTable(
              ['Title', 'Assigned', 'Priority', 'Status'],
              (data.recentTasks || []).map(task => [task.title, task.assignedUserName || '-', renderStatusBadge(task.priority), renderStatusBadge(task.status)]),
              'No tasks yet'
            )}
          </div>
          <div class="content-card">
            <div class="card-title-row"><div><h5>Recent Alerts</h5><div class="text-muted small">System notifications and issues</div></div><span class="kpi-chip">${(data.recentAlerts || []).length} active items</span></div>
            <div class="list-group list-group-flush list-group-clean">
              ${(data.recentAlerts || []).length ? (data.recentAlerts || []).map(alert => `
                <div class="list-group-item d-flex justify-content-between align-items-start gap-3">
                  <div>
                    <div class="fw-semibold">${escapeHtml(alert.title)}</div>
                    <div class="small text-muted">${escapeHtml(alert.message || '')}</div>
                  </div>
                  <div class="d-flex gap-2">${renderStatusBadge(alert.priority)} ${renderStatusBadge(alert.status)}</div>
                </div>
              `).join('') : '<div class="empty-state">No alerts yet</div>'}
            </div>
          </div>
        </div>

        <div class="section-grid two-col">
          <div class="content-card">
            <div class="card-title-row"><div><h5>Recent Validations</h5><div class="text-muted small">AI versus sensor comparison history</div></div></div>
            ${renderSimpleTable(
              ['Bin', 'AI', 'Sensor', 'Result'],
              (data.recentValidations || []).map(item => [item.binCode || '-', item.aiLevel, item.sensorLevel, renderStatusBadge(item.match)]),
              'No validation records yet'
            )}
          </div>
          <div class="content-card">
            <div class="card-title-row"><div><h5>Quick Actions</h5><div class="text-muted small">Jump back into the most common workflows</div></div></div>
            <div class="quick-action-grid">
              <button class="btn btn-success btn-lg" data-route-jump="${state.user.role === 'admin' ? 'users' : 'bins'}">Manage ${state.user.role === 'admin' ? 'Users' : 'Bins'}</button>
              <button class="btn btn-outline-success btn-lg" data-route-jump="tasks">Open Tasks</button>
              <button class="btn btn-outline-secondary btn-lg" data-route-jump="alerts">Review Alerts</button>
              <button class="btn btn-outline-danger btn-lg" data-route-jump="validations">AI Validation</button>
              ${state.user.role === 'staff' ? '' : '<button class="btn btn-outline-dark btn-lg" data-route-jump="reports">Open Reports</button>'}
            </div>
            <div class="mt-4">
              ${renderSimpleTable(
                ['Report', 'Covers', 'Use'],
                [
                  ['Users', 'Accounts, roles, and city assignments', 'Audit staff and admin records'],
                  ['Bins', 'Locations, status, and assignments', 'Track infrastructure health'],
                  ['Tasks', 'Assignments, priorities, and due dates', 'Review work execution'],
                  ['Validation Runs', 'AI vs sensor results and reviews', 'Monitor validation quality']
                ],
                'No report categories available'
              )}
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function renderUsersPage(users) {
    const roleOptions = optionTags(state.lookups?.roles || ['city_head', 'staff'], null, value => titleCase(value.replace('_', ' ')));
    const statusOptions = optionTags(state.lookups?.userStatusOptions || ['active', 'inactive'], 'active', value => titleCase(value));

    return `
      <div class="section-grid">
        ${renderPageHero('User Management', 'The admin can now create city heads and staff with proper stored credentials.')}
        ${renderMetricCards([
          { label: 'Total Users', value: users.length, subtext: 'Stored in SQLite' },
          { label: 'Admins', value: users.filter(user => user.role === 'admin').length, subtext: 'System admins' },
          { label: 'City Heads', value: users.filter(user => user.role === 'city_head').length, subtext: 'Area managers' },
          { label: 'Staff', value: users.filter(user => user.role === 'staff').length, subtext: 'Field team' }
        ])}
        ${renderInlineFeedback('user-feedback')}
        <div class="section-grid two-col">
        <div class="content-card">
          <div class="card-title-row"><div><h5>Create / Edit User</h5><div class="text-muted small">Admin can add city heads and staff with real credentials</div></div></div>
          <form id="user-form" class="row g-3">
            <input type="hidden" name="id" />
            <div class="col-md-6"><label class="form-label">Full Name</label><input name="fullName" class="form-control" required /></div>
            <div class="col-md-6"><label class="form-label">Username</label><input name="username" class="form-control" required /></div>
            <div class="col-md-6"><label class="form-label">Password</label><input name="password" type="password" class="form-control" placeholder="Required for new user" /></div>
            <div class="col-md-6"><label class="form-label">Role</label><select name="role" class="form-select">${roleOptions}</select></div>
            <div class="col-md-6"><label class="form-label">Email</label><input name="email" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Phone</label><input name="phone" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">City</label><input name="city" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Zone</label><input name="zone" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Status</label><select name="status" class="form-select">${statusOptions}</select></div>
            <div class="col-md-6"><label class="form-label">Meta</label><input name="meta" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Employee ID</label><input name="employeeId" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Shift</label><input name="shiftName" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Vehicle</label><input name="vehicle" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Supervisor</label><input name="supervisorName" class="form-control" /></div>
            <div class="col-md-6"><label class="form-label">Emergency Contact</label><input name="emergencyContact" class="form-control" /></div>
            <div class="col-12"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="3"></textarea></div>
            <div class="col-12 d-flex gap-2 justify-content-end">
              <button type="button" id="user-form-reset" class="btn btn-outline-secondary">Clear</button>
              <button type="submit" class="btn btn-success">Save User</button>
            </div>
          </form>
        </div>

        <div class="content-card">
          <div class="card-title-row"><div><h5>Users</h5><div class="text-muted small">Stored in SQLite, no hardcoded credentials</div></div></div>
          ${renderEntityTable(
            ['ID', 'Name', 'Username', 'Role', 'Status', 'Zone', 'Actions'],
            users.map(user => [
              user.id,
              user.fullName,
              user.username,
              renderStatusBadge(titleCase(user.role.replace('_', ' '))),
              renderStatusBadge(user.status),
              user.zone || '-',
              actionButtons('user', user.id)
            ]),
            'No users in the database yet',
            { datatable: true, tableId: 'users-table', searchPlaceholder: 'Search users' }
          )}
        </div>
        </div>
      </div>
    `;
  }

  function renderBinsPage(bins) {
    const userOptions = optionTags((state.lookups?.users || []).filter(user => user.role !== 'admin'), null, user => `${user.fullName} (${user.role})`);
    const statusOptions = optionTags(state.lookups?.binStatusOptions || [], 'active', value => titleCase(value));

    const form = state.user.role === 'staff' ? '' : `
      <div class="content-card">
        <div class="card-title-row"><div><h5>Create / Edit Bin</h5><div class="text-muted small">Manage bin master data in SQLite</div></div></div>
        <form id="bin-form" class="row g-3">
          <input type="hidden" name="id" />
          <div class="col-md-6"><label class="form-label">Bin Code</label><input name="binCode" class="form-control" required /></div>
          <div class="col-md-6"><label class="form-label">Location</label><input name="location" class="form-control" required /></div>
          <div class="col-md-6"><label class="form-label">Zone</label><input name="zone" class="form-control" /></div>
          <div class="col-md-6"><label class="form-label">Capacity (liters)</label><input name="capacityLiters" type="number" class="form-control" /></div>
          <div class="col-md-6"><label class="form-label">Status</label><select name="status" class="form-select">${statusOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Level</label><input name="level" class="form-control" placeholder="low / medium / high / unknown" /></div>
          <div class="col-md-6"><label class="form-label">Sensor Status</label><input name="sensorStatus" class="form-control" /></div>
          <div class="col-md-6"><label class="form-label">Assigned User</label><select name="assignedUserId" class="form-select"><option value="">Unassigned</option>${userOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Last Cleaned</label><input name="lastCleaned" class="form-control" placeholder="YYYY-MM-DD" /></div>
          <div class="col-12"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="3"></textarea></div>
          <div class="col-12 d-flex gap-2 justify-content-end">
            <button type="button" id="bin-form-reset" class="btn btn-outline-secondary">Clear</button>
            <button type="submit" class="btn btn-success">Save Bin</button>
          </div>
        </form>
      </div>`;

    return `
      <div class="section-grid">
        ${renderPageHero(state.user.role === 'staff' ? 'Assigned Bins' : 'Bin Management', 'Keep the cleaner card-based layout while editing live records.')}
        ${renderMetricCards([
          { label: 'Total Bins', value: bins.length, subtext: 'Visible in this account' },
          { label: 'Active', value: bins.filter(bin => bin.status === 'active').length, subtext: 'Operational bins' },
          { label: 'Maintenance', value: bins.filter(bin => bin.status === 'maintenance').length, subtext: 'Need service' },
          { label: 'Assigned', value: bins.filter(bin => !!bin.assignedUserId).length, subtext: 'Allocated to staff or city head' }
        ])}
        ${renderInlineFeedback('bin-feedback')}
        <div class="section-grid ${state.user.role === 'staff' ? '' : 'two-col'}">
        ${form}
        <div class="content-card">
          <div class="card-title-row"><div><h5>${state.user.role === 'staff' ? 'My Bins' : 'Bins'}</h5><div class="text-muted small">Live bin list from SQLite</div></div></div>
          ${renderEntityTable(
            ['Code', 'Location', 'Zone', 'Status', 'Level', 'Assigned', 'Actions'],
            bins.map(bin => [
              bin.binCode,
              bin.location,
              bin.zone || '-',
              renderStatusBadge(bin.status),
              renderStatusBadge(bin.level),
              bin.assignedUserName || '-',
              state.user.role === 'staff' ? '-' : actionButtons('bin', bin.id)
            ]),
            'No bins in the database yet',
            { datatable: true, tableId: 'bins-table', searchPlaceholder: 'Search bins' }
          )}
        </div>
        </div>
      </div>
    `;
  }

  function renderTasksPage(tasks) {
    const userOptions = optionTags((state.lookups?.users || []).filter(user => user.role !== 'admin'), null, user => `${user.fullName} (${user.role})`);
    const binOptions = optionTags(state.lookups?.bins || [], null, bin => `${bin.binCode} - ${bin.location}`);
    const priorityOptions = optionTags(state.lookups?.taskPriorityOptions || [], 'medium', value => titleCase(value));
    const statusOptions = optionTags(state.lookups?.taskStatusOptions || [], 'pending', value => titleCase(value.replace('_', ' ')));

    const form = state.user.role === 'staff' ? '' : `
      <div class="content-card">
        <div class="card-title-row"><div><h5>Create / Edit Task</h5><div class="text-muted small">Assign work to staff and track status</div></div></div>
        <form id="task-form" class="row g-3">
          <input type="hidden" name="id" />
          <div class="col-md-6"><label class="form-label">Title</label><input name="title" class="form-control" required /></div>
          <div class="col-md-6"><label class="form-label">Zone</label><input name="zone" class="form-control" /></div>
          <div class="col-md-6"><label class="form-label">Priority</label><select name="priority" class="form-select">${priorityOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Status</label><select name="status" class="form-select">${statusOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Assigned User</label><select name="assignedUserId" class="form-select"><option value="">Unassigned</option>${userOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Bin</label><select name="binId" class="form-select"><option value="">No bin selected</option>${binOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Due At</label><input name="dueAt" class="form-control" placeholder="YYYY-MM-DD HH:MM" /></div>
          <div class="col-12"><label class="form-label">Description</label><textarea name="description" class="form-control" rows="3"></textarea></div>
          <div class="col-12"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="2"></textarea></div>
          <div class="col-12 d-flex gap-2 justify-content-end">
            <button type="button" id="task-form-reset" class="btn btn-outline-secondary">Clear</button>
            <button type="submit" class="btn btn-success">Save Task</button>
          </div>
        </form>
      </div>`;

    return `
      <div class="section-grid">
        ${renderPageHero(state.user.role === 'staff' ? 'My Tasks' : 'Task Management', 'Track field work with the richer operations layout and clear action messages.')}
        ${renderMetricCards([
          { label: 'Total Tasks', value: tasks.length, subtext: 'Visible in this account' },
          { label: 'Pending', value: tasks.filter(task => task.status === 'pending').length, subtext: 'Waiting to start' },
          { label: 'In Progress', value: tasks.filter(task => task.status === 'in_progress').length, subtext: 'Active field work' },
          { label: 'Completed', value: tasks.filter(task => task.status === 'completed').length, subtext: 'Finished tasks' }
        ])}
        ${renderInlineFeedback('task-feedback')}
        <div class="section-grid ${state.user.role === 'staff' ? '' : 'two-col'}">
        ${form}
        <div class="content-card">
          <div class="card-title-row"><div><h5>${state.user.role === 'staff' ? 'My Tasks' : 'Tasks'}</h5><div class="text-muted small">Task records now come from SQLite</div></div><span class="kpi-chip">${tasks.length} records</span></div>
          ${renderEntityTable(
            ['Title', 'Assigned', 'Priority', 'Status', 'Due', 'Bin', 'Actions'],
            tasks.map(task => [
              task.title,
              task.assignedUserName || '-',
              renderStatusBadge(task.priority),
              renderStatusBadge(task.status),
              task.dueAt || '-',
              task.binCode || '-',
              state.user.role === 'staff' ? staffTaskActions(task) : actionButtons('task', task.id)
            ]),
            'No tasks in the database yet',
            { datatable: true, tableId: 'tasks-table', searchPlaceholder: 'Search tasks' }
          )}
        </div>
        </div>
      </div>
    `;
  }

  function renderAlertsPage(alerts) {
    const userOptions = optionTags((state.lookups?.users || []).filter(user => user.role !== 'admin'), null, user => `${user.fullName} (${user.role})`);
    const binOptions = optionTags(state.lookups?.bins || [], null, bin => `${bin.binCode} - ${bin.location}`);
    const priorityOptions = optionTags(state.lookups?.alertPriorityOptions || [], 'medium', value => titleCase(value));
    const statusOptions = optionTags(state.lookups?.alertStatusOptions || [], 'open', value => titleCase(value));

    const form = state.user.role === 'staff' ? '' : `
      <div class="content-card">
        <div class="card-title-row"><div><h5>Create / Edit Alert</h5><div class="text-muted small">Send alerts to teams or link them to bins</div></div></div>
        <form id="alert-form" class="row g-3">
          <input type="hidden" name="id" />
          <div class="col-md-6"><label class="form-label">Title</label><input name="title" class="form-control" required /></div>
          <div class="col-md-6"><label class="form-label">Priority</label><select name="priority" class="form-select">${priorityOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Status</label><select name="status" class="form-select">${statusOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Target User</label><select name="userId" class="form-select"><option value="">All users</option>${userOptions}</select></div>
          <div class="col-md-6"><label class="form-label">Bin</label><select name="binId" class="form-select"><option value="">No bin</option>${binOptions}</select></div>
          <div class="col-12"><label class="form-label">Message</label><textarea name="message" class="form-control" rows="3" required></textarea></div>
          <div class="col-12 d-flex gap-2 justify-content-end">
            <button type="button" id="alert-form-reset" class="btn btn-outline-secondary">Clear</button>
            <button type="submit" class="btn btn-success">Save Alert</button>
          </div>
        </form>
      </div>`;

    return `
      <div class="section-grid">
        ${renderPageHero('Alerts', 'Surface operational issues quickly and keep the response workflow easy to manage.')}
        ${renderMetricCards([
          { label: 'Total Alerts', value: alerts.length, subtext: 'Stored in SQLite' },
          { label: 'Open', value: alerts.filter(alert => alert.status === 'open').length, subtext: 'Require attention' },
          { label: 'Resolved', value: alerts.filter(alert => alert.status === 'resolved').length, subtext: 'Closed issues' },
          { label: 'High Priority', value: alerts.filter(alert => alert.priority === 'high').length, subtext: 'Urgent notifications' }
        ])}
        ${renderInlineFeedback('alert-feedback')}
        <div class="section-grid ${state.user.role === 'staff' ? '' : 'two-col'}">
        ${form}
        <div class="content-card">
          <div class="card-title-row"><div><h5>Alerts</h5><div class="text-muted small">Status can be updated by the receiving user</div></div><span class="kpi-chip">${alerts.length} records</span></div>
          ${renderEntityTable(
            ['Title', 'Priority', 'Status', 'User', 'Bin', 'Actions'],
            alerts.map(alert => [
              alert.title,
              renderStatusBadge(alert.priority),
              renderStatusBadge(alert.status),
              alert.userName || 'All users',
              alert.binCode || '-',
              state.user.role === 'staff' ? staffAlertActions(alert) : actionButtons('alert', alert.id)
            ]),
            'No alerts in the database yet',
            { datatable: true, tableId: 'alerts-table', searchPlaceholder: 'Search alerts' }
          )}
        </div>
        </div>
      </div>
    `;
  }

  function renderReportsPage(data) {
    const datasets = data || {};
    const users = filterGeneratedReportItems(datasets.users || [], item => item.createdAt);
    const bins = filterGeneratedReportItems(datasets.bins || [], item => item.createdAt);
    const tasks = filterGeneratedReportItems(datasets.tasks || [], item => item.createdAt);
    const validations = filterGeneratedReportItems(datasets.validations || [], item => item.createdAt || item.timestamp);
    const pageLength = hasActiveReportFilter() ? -1 : 8;

    return `
      <div class="section-grid">
        ${renderPageHero('Reports', 'Generate live report tables for users, bins, tasks, and validation runs with a shared date range.')}
        <div id="reports-metrics">${renderMetricCards(buildGeneratedReportMetrics({ users, bins, tasks, validations }))}</div>
        <div class="content-card report-filter-card">
          <div class="card-title-row mb-0">
            <div>
              <h5>Generated Reports Filter</h5>
              <div class="text-muted small">Set a start date and end date to filter every report below by creation date.</div>
            </div>
            <span class="kpi-chip" id="reports-count-chip">${buildGeneratedReportCountChip({ users, bins, tasks, validations })}</span>
          </div>
          <div class="report-filter-grid mt-4">
            <div>
              <label for="report-filter-from" class="form-label">Start Date</label>
              <input id="report-filter-from" type="date" class="form-control" value="${escapeHtml(state.reportDateFilter.from)}" />
            </div>
            <div>
              <label for="report-filter-to" class="form-label">End Date</label>
              <input id="report-filter-to" type="date" class="form-control" value="${escapeHtml(state.reportDateFilter.to)}" />
            </div>
            <div class="report-filter-actions">
              <button type="button" id="report-filter-clear" class="btn btn-outline-secondary">Clear Filter</button>
            </div>
            <div class="report-filter-summary text-muted small" id="reports-filter-summary">${buildGeneratedReportSummary({ users, bins, tasks, validations })}</div>
          </div>
        </div>

        <div class="section-grid two-col">
          <div class="content-card">
            <div class="card-title-row"><div><h5>Users Report</h5><div class="text-muted small">User accounts within the selected date range</div></div></div>
            ${renderEntityTable(
              ['ID', 'Name', 'Username', 'Role', 'Status', 'City', 'Zone', 'Created'],
              users.map(user => [user.id, user.fullName, user.username, renderStatusBadge(titleCase(user.role.replace('_', ' '))), renderStatusBadge(user.status), user.city || '-', user.zone || '-', formatDateTime(user.createdAt)]),
              'No users found for the selected date range',
              { datatable: true, tableId: 'report-users-table', searchPlaceholder: 'Search users report', pageLength, exportable: true, exportTitle: 'Users Report' }
            )}
          </div>

          <div class="content-card">
            <div class="card-title-row"><div><h5>Bins Report</h5><div class="text-muted small">Bin inventory and assignment status</div></div></div>
            ${renderEntityTable(
              ['Code', 'Location', 'Zone', 'Status', 'Level', 'Assigned', 'Created'],
              bins.map(bin => [bin.binCode, bin.location, bin.zone || '-', renderStatusBadge(bin.status), renderStatusBadge(bin.level), bin.assignedUserName || '-', formatDateTime(bin.createdAt)]),
              'No bins found for the selected date range',
              { datatable: true, tableId: 'report-bins-table', searchPlaceholder: 'Search bins report', pageLength, exportable: true, exportTitle: 'Bins Report' }
            )}
          </div>
        </div>

        <div class="section-grid two-col">
          <div class="content-card">
            <div class="card-title-row"><div><h5>Tasks Report</h5><div class="text-muted small">Task execution and due date tracking</div></div></div>
            ${renderEntityTable(
              ['Title', 'Assigned', 'Priority', 'Status', 'Bin', 'Due', 'Created'],
              tasks.map(task => [task.title, task.assignedUserName || '-', renderStatusBadge(task.priority), renderStatusBadge(task.status), task.binCode || '-', task.dueAt || '-', formatDateTime(task.createdAt)]),
              'No tasks found for the selected date range',
              { datatable: true, tableId: 'report-tasks-table', searchPlaceholder: 'Search tasks report', pageLength, exportable: true, exportTitle: 'Tasks Report' }
            )}
          </div>

          <div class="content-card">
            <div class="card-title-row"><div><h5>Validation Runs Report</h5><div class="text-muted small">AI and sensor validation history</div></div></div>
            ${renderEntityTable(
              ['Bin', 'AI Level', 'Sensor Level', 'Result', 'Review', 'Created By', 'Created'],
              validations.map(item => [item.binCode || '-', item.aiLevel || '-', item.sensorLevel || '-', renderStatusBadge(item.match), renderStatusBadge(item.reviewStatus), item.createdByName || '-', formatDateTime(item.createdAt || item.timestamp)]),
              'No validation runs found for the selected date range',
              { datatable: true, tableId: 'report-validations-table', searchPlaceholder: 'Search validations report', pageLength, exportable: true, exportTitle: 'Validation Runs Report' }
            )}
          </div>
        </div>
      </div>
    `;
  }

  function renderValidationResultPanel() {
    if (!state.validationResult) {
      return `
        <div id="validation-result" class="content-card mt-3">
          <div class="text-muted small">Latest comparison</div>
          <div class="fw-semibold mt-1">Run a validation to see the AI result, confidence, and ultrasonic comparison here.</div>
        </div>
      `;
    }

    const result = state.validationResult;
    const tone = result.match === 'Match' ? 'success' : result.match === 'Mismatch' ? 'danger' : 'warning';
    const probabilities = Object.entries(result.probabilities || {})
      .sort((left, right) => right[1] - left[1])
      .slice(0, 3);

    return `
      <div id="validation-result" class="alert alert-${tone} border mt-3 mb-0">
        <div class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
          <div>
            <div class="small text-uppercase fw-semibold mb-1">Latest comparison</div>
            <h5 class="mb-1">${escapeHtml(result.match || 'Unavailable')}</h5>
            <div>AI level: <strong>${escapeHtml(result.aiLevel || 'unknown')}</strong> at <strong>${escapeHtml(result.confidence ?? '-')}%</strong> confidence</div>
            <div>Sensor level: <strong>${escapeHtml(result.sensorLevel || 'unknown')}</strong>${result.sensorDistanceCm !== null && result.sensorDistanceCm !== undefined ? ` at <strong>${escapeHtml(result.sensorDistanceCm)} cm</strong>` : ''}</div>
          </div>
          <div class="d-flex gap-2 flex-wrap">
            ${probabilities.map(([label, value]) => `<span class="status-badge status-info">${escapeHtml(label)} ${escapeHtml(value)}%</span>`).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function renderValidationsPage(validations) {
    const binOptions = optionTags(state.lookups?.bins || [], null, bin => `${bin.binCode} - ${bin.location}`);
    const matches = validations.filter(item => item.match === 'Match').length;
    const mismatches = validations.filter(item => item.match === 'Mismatch').length;
    const pendingReview = validations.filter(item => item.reviewStatus === 'new').length;

    return `
      <div class="section-grid">
        ${renderPageHero('AI Validation', 'Upload a dustbin image, compare it with the ultrasonic reading, and review every stored result from one place.')}
        ${renderMetricCards([
          { label: 'Total Runs', value: validations.length, subtext: 'Saved validation history' },
          { label: 'Matches', value: matches, subtext: 'AI and sensor agreed' },
          { label: 'Mismatches', value: mismatches, subtext: 'Need investigation' },
          { label: 'Pending Review', value: pendingReview, subtext: 'Still marked as new' }
        ])}
        ${renderInlineFeedback('validation-feedback')}
        <div class="section-grid two-col">
        <div class="content-card">
          <div class="card-title-row"><div><h5>Run Validation</h5><div class="text-muted small">Upload an image and compare it with the ultrasonic sensor reading</div></div><span class="kpi-chip">Image + Sensor</span></div>
          <form id="validation-form" class="row g-3">
            <div class="col-md-6"><label class="form-label">Bin</label><select name="bin_id" class="form-select"><option value="">Select bin</option>${binOptions}</select></div>
            <div class="col-md-6"><label class="form-label">Location</label><input name="location" class="form-control" placeholder="Optional if bin already selected" /></div>
            <div class="col-md-6"><label class="form-label">Live Sensor Reading</label><input id="sensor-level-output" class="form-control" value="Waiting for sensor..." readonly /></div>
            <div class="col-md-6"><label class="form-label">Sensor Source</label><input id="sensor-source-output" class="form-control" value="Checking sensor source..." readonly /></div>
            <div class="col-md-6"><label class="form-label">Manual Sensor Distance (cm)</label><input name="sensor_distance_cm" class="form-control" type="number" step="0.01" /></div>
            <div class="col-md-6"><label class="form-label">Upload Image</label><input name="image" class="form-control" type="file" accept="image/*" required /></div>
            <div class="col-12 d-flex gap-2 justify-content-end">
              <button type="submit" class="btn btn-success">Run Validation</button>
            </div>
          </form>
          ${renderValidationResultPanel()}
        </div>

        <div class="content-card">
          <div class="card-title-row"><div><h5>Validation History</h5><div class="text-muted small">Records are stored in SQLite with review tracking</div></div><span class="kpi-chip">${validations.length} records</span></div>
          ${renderEntityTable(
            ['Bin', 'AI', 'Sensor', 'Result', 'Review', 'Actions'],
            validations.map(item => [
              item.binCode || '-',
              item.aiLevel,
              `${item.sensorLevel}${item.sensorDistanceCm !== null && item.sensorDistanceCm !== undefined ? ` (${item.sensorDistanceCm} cm)` : ''}`,
              renderStatusBadge(item.match),
              renderStatusBadge(item.reviewStatus),
              validationActions(item)
            ]),
            'No validation runs yet',
            { datatable: true, tableId: 'validations-table', searchPlaceholder: 'Search validations' }
          )}
        </div>
        </div>
      </div>
    `;
  }

  function renderProfilePage(user) {
    return `
      <div class="section-grid">
        ${renderPageHero('Profile', 'Keep your account details up to date without leaving the main dashboard experience.')}
        ${renderMetricCards([
          { label: 'Role', value: titleCase((user.role || '').replace('_', ' ')), subtext: 'Current access level' },
          { label: 'Status', value: titleCase(user.status || 'active'), subtext: 'Account state' },
          { label: 'City', value: user.city || 'Not set', subtext: 'Assigned city' },
          { label: 'Zone', value: user.zone || 'Not set', subtext: 'Assigned zone' }
        ])}
        ${renderInlineFeedback('profile-feedback')}
        <div class="section-grid two-col">
          <div class="content-card">
            <div class="d-flex align-items-center gap-3 mb-4">
              <div class="profile-avatar"><i class="bi bi-person"></i></div>
              <div>
                <h5 class="mb-1">${escapeHtml(user.fullName || 'User')}</h5>
                <div class="text-muted">${escapeHtml(user.username || '')}</div>
                <div class="mt-2">${renderStatusBadge(titleCase((user.role || '').replace('_', ' ')))} ${renderStatusBadge(user.status || 'active')}</div>
              </div>
            </div>
            <div class="section-grid two-col">
              <div class="soft-stat"><div class="soft-stat-label">Employee ID</div><div class="soft-stat-value">${escapeHtml(user.employeeId || 'N/A')}</div></div>
              <div class="soft-stat"><div class="soft-stat-label">Shift</div><div class="soft-stat-value">${escapeHtml(user.shiftName || 'N/A')}</div></div>
              <div class="soft-stat"><div class="soft-stat-label">Vehicle</div><div class="soft-stat-value">${escapeHtml(user.vehicle || 'N/A')}</div></div>
              <div class="soft-stat"><div class="soft-stat-label">Supervisor</div><div class="soft-stat-value">${escapeHtml(user.supervisorName || 'N/A')}</div></div>
            </div>
          </div>

          <div class="content-card">
            <div class="card-title-row"><div><h5>Update Profile</h5><div class="text-muted small">Changes are saved directly into SQLite</div></div></div>
            <form id="profile-form" class="row g-3">
              <div class="col-md-6"><label class="form-label">Full Name</label><input name="fullName" class="form-control" value="${escapeHtml(user.fullName || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Email</label><input name="email" class="form-control" value="${escapeHtml(user.email || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Phone</label><input name="phone" class="form-control" value="${escapeHtml(user.phone || '')}" /></div>
              <div class="col-md-6"><label class="form-label">City</label><input name="city" class="form-control" value="${escapeHtml(user.city || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Zone</label><input name="zone" class="form-control" value="${escapeHtml(user.zone || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Meta</label><input name="meta" class="form-control" value="${escapeHtml(user.meta || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Employee ID</label><input name="employeeId" class="form-control" value="${escapeHtml(user.employeeId || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Shift</label><input name="shiftName" class="form-control" value="${escapeHtml(user.shiftName || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Vehicle</label><input name="vehicle" class="form-control" value="${escapeHtml(user.vehicle || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Supervisor</label><input name="supervisorName" class="form-control" value="${escapeHtml(user.supervisorName || '')}" /></div>
              <div class="col-md-6"><label class="form-label">Emergency Contact</label><input name="emergencyContact" class="form-control" value="${escapeHtml(user.emergencyContact || '')}" /></div>
              <div class="col-md-6"><label class="form-label">New Password</label><input name="password" type="password" class="form-control" placeholder="Leave blank to keep current password" /></div>
              <div class="col-12"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="4">${escapeHtml(user.notes || '')}</textarea></div>
              <div class="col-12 d-flex justify-content-end"><button type="submit" class="btn btn-success">Save Profile</button></div>
            </form>
          </div>
        </div>
      </div>
    `;
  }

  function renderSimpleTable(headers, rows, emptyText) {
    return renderEntityTable(headers, rows, emptyText);
  }

  function renderEntityTable(headers, rows, emptyText, options = {}) {
    const attributes = [];
    if (options.tableId) attributes.push(`id="${escapeHtml(options.tableId)}"`);
    if (options.datatable) attributes.push('data-datatable="true"');
    if (options.pageLength) attributes.push(`data-page-length="${escapeHtml(options.pageLength)}"`);
    if (options.searchPlaceholder) attributes.push(`data-search-placeholder="${escapeHtml(options.searchPlaceholder)}"`);
    if (options.exportable) attributes.push('data-exportable="true"');
    if (options.exportTitle) attributes.push(`data-export-title="${escapeHtml(options.exportTitle)}"`);

    return `
      <div class="table-responsive">
        <table class="table align-middle ${escapeHtml(options.tableClass || '')}" ${attributes.join(' ')}>
          <thead><tr>${headers.map(header => `<th>${header}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.length ? rows.map(row => {
              const normalized = Array.isArray(row) ? { cells: row } : row;
              const rowAttributes = Object.entries(normalized.attributes || {})
                .map(([key, value]) => `${key}="${escapeHtml(value)}"`)
                .join(' ');
              const classAttribute = normalized.className ? ` class="${escapeHtml(normalized.className)}"` : '';
              const joinedAttributes = `${classAttribute}${rowAttributes ? ` ${rowAttributes}` : ''}`;
              return `<tr${joinedAttributes}>${(normalized.cells || []).map(cell => `<td>${cell}</td>`).join('')}</tr>`;
            }).join('') : `<tr><td colspan="${headers.length}" class="text-center text-muted py-4">${emptyText}</td></tr>`}
          </tbody>
        </table>
      </div>
    `;
  }

  function initializeDataTables() {
    const instances = new Map();
    if (typeof window.DataTable !== 'function') return instances;

    document.querySelectorAll('table[data-datatable="true"]').forEach(table => {
      if (table.querySelector('tbody td[colspan]')) return;

      const rowCount = table.querySelectorAll('tbody tr').length;
      const rawPageLength = Number(table.dataset.pageLength || 8);
      const pageLength = Number.isNaN(rawPageLength) ? 8 : rawPageLength;
      const exportable = table.dataset.exportable === 'true';
      const lastHeaderText = table.querySelector('thead th:last-child')?.textContent?.trim().toLowerCase() || '';
      const columnDefs = lastHeaderText === 'actions' ? [{ targets: -1, orderable: false, searchable: false }] : [];
      const instance = new window.DataTable(table, {
        order: [],
        autoWidth: false,
        pageLength: pageLength === -1 ? rowCount : pageLength,
        lengthMenu: [5, 8, 10, 25, 50],
        paging: pageLength !== -1 && rowCount > pageLength,
        info: rowCount > 0,
        columnDefs,
        layout: exportable ? {
          topStart: {
            buttons: [
              { extend: 'copyHtml5', title: table.dataset.exportTitle || 'Report Export', className: 'report-export-btn btn btn-outline-secondary btn-sm' },
              { extend: 'csvHtml5', title: table.dataset.exportTitle || 'Report Export', className: 'report-export-btn btn btn-outline-secondary btn-sm' },
              { extend: 'excelHtml5', title: table.dataset.exportTitle || 'Report Export', className: 'report-export-btn btn btn-outline-secondary btn-sm' },
              { extend: 'print', title: table.dataset.exportTitle || 'Report Export', className: 'report-export-btn btn btn-outline-secondary btn-sm' }
            ]
          },
          topEnd: 'search',
          bottomStart: rowCount > 0 ? 'info' : null,
          bottomEnd: pageLength !== -1 && rowCount > pageLength ? 'paging' : null
        } : undefined,
        language: {
          search: '',
          searchPlaceholder: table.dataset.searchPlaceholder || 'Search records',
          lengthMenu: 'Show _MENU_ rows',
          info: 'Showing _START_ to _END_ of _TOTAL_ rows',
          infoEmpty: 'No rows available'
        }
      });

      state.dataTables.push(instance);
      if (table.id) instances.set(table.id, instance);
    });

    bindReportExportButtons();
    return instances;
  }

  function bindReportExportButtons() {
    document.querySelectorAll('.report-export-btn').forEach(button => {
      if (button.dataset.exportStyled === 'true') return;

      const setState = active => {
        const rootStyle = getComputedStyle(document.documentElement);
        const primary = rootStyle.getPropertyValue('--sw-primary').trim() || '#2e7d32';
        const primaryDark = rootStyle.getPropertyValue('--sw-primary-dark').trim() || '#1b5e20';

        button.style.backgroundImage = 'none';
        button.style.boxShadow = 'none';
        button.style.backgroundColor = active ? primary : 'transparent';
        button.style.color = active ? '#ffffff' : primaryDark;
        button.style.borderColor = active ? primary : 'rgba(46, 125, 50, 0.24)';
      };

      const activate = () => setState(true);
      const deactivate = () => setState(false);

      setState(false);
      button.addEventListener('mouseenter', activate);
      button.addEventListener('mouseleave', deactivate);
      button.addEventListener('focus', activate);
      button.addEventListener('blur', deactivate);
      button.addEventListener('mousedown', activate);
      button.addEventListener('mouseup', () => {
        if (!button.matches(':hover') && document.activeElement !== button) deactivate();
      });

      button.dataset.exportStyled = 'true';
    });
  }

  function summarizeByKey(items, key) {
    const summary = {};
    items.forEach(item => {
      const label = titleCase(String(item[key] || 'unknown').replace('_', ' '));
      summary[label] = (summary[label] || 0) + 1;
    });
    return Object.keys(summary).length ? summary : { None: 0 };
  }

  function buildGeneratedReportMetrics(datasets) {
    return [
      { label: 'Users', value: datasets.users.length, subtext: 'Filtered user records' },
      { label: 'Bins', value: datasets.bins.length, subtext: 'Filtered bin records' },
      { label: 'Tasks', value: datasets.tasks.length, subtext: 'Filtered task records' },
      { label: 'Validation Runs', value: datasets.validations.length, subtext: 'Filtered AI validation records' }
    ];
  }

  function buildGeneratedReportCountChip(datasets) {
    const total = datasets.users.length + datasets.bins.length + datasets.tasks.length + datasets.validations.length;
    return `${total} filtered rows`;
  }

  function buildGeneratedReportSummary(datasets) {
    const range = normalizedDateRange(state.reportDateFilter.from, state.reportDateFilter.to);
    const summary = `${datasets.users.length} users, ${datasets.bins.length} bins, ${datasets.tasks.length} tasks, and ${datasets.validations.length} validation runs`;

    if (!range.from && !range.to) {
      return `Showing all available rows: ${summary}. Apply a date range to narrow every report table and export the result.`;
    }

    const start = range.from ? formatInputDate(range.from) : 'the beginning';
    const end = range.to ? formatInputDate(range.to) : 'today';
    return `Showing ${summary} from ${start} to ${end}. Export buttons are available above each table.`;
  }

  function hasActiveReportFilter() {
    return Boolean(state.reportDateFilter.from || state.reportDateFilter.to);
  }

  function filterGeneratedReportItems(items, dateGetter) {
    const range = normalizedDateRange(state.reportDateFilter.from, state.reportDateFilter.to);
    return items.filter(item => isDateWithinRange(extractDateKey(dateGetter(item)), range.from, range.to));
  }

  function normalizedDateRange(from, to) {
    if (from && to && from > to) {
      return { from: to, to: from };
    }
    return { from: from || '', to: to || '' };
  }

  function isDateWithinRange(dateValue, from, to) {
    if (!dateValue) return !from && !to;
    if (from && dateValue < from) return false;
    if (to && dateValue > to) return false;
    return true;
  }

  function extractDateKey(value) {
    const text = String(value || '').trim();
    const match = text.match(/^(\d{4}-\d{2}-\d{2})/);
    if (match) return match[1];
    if (!text) return '';

    const parsed = new Date(text);
    if (Number.isNaN(parsed.getTime())) return '';

    const year = parsed.getFullYear();
    const month = String(parsed.getMonth() + 1).padStart(2, '0');
    const day = String(parsed.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
  }

  function formatInputDate(value) {
    if (!value) return '';
    const [year, month, day] = String(value).split('-').map(Number);
    if (!year || !month || !day) return value;

    return new Date(year, month - 1, day).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  }

  function optionTags(items, selectedValue, labelGetter) {
    return items.map(item => {
      const value = typeof item === 'string' ? item : item.id;
      const label = typeof item === 'string' ? (labelGetter ? labelGetter(item) : item) : (labelGetter ? labelGetter(item) : item.fullName || item.binCode);
      const selected = String(value) === String(selectedValue || '') ? 'selected' : '';
      return `<option value="${escapeHtml(value)}" ${selected}>${escapeHtml(label)}</option>`;
    }).join('');
  }

  function actionButtons(type, id) {
    return `
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary btn-sm" data-action="edit-${type}" data-id="${id}">Edit</button>
        <button class="btn btn-outline-danger btn-sm" data-action="delete-${type}" data-id="${id}">Delete</button>
      </div>
    `;
  }

  function staffTaskActions(task) {
    const options = optionTags(state.lookups?.taskStatusOptions || [], task.status, value => titleCase(value.replace('_', ' ')));
    return `
      <div class="d-flex gap-2">
        <select class="form-select form-select-sm" data-action="staff-task-status" data-id="${task.id}">${options}</select>
        <button class="btn btn-outline-success btn-sm" data-action="save-staff-task" data-id="${task.id}">Save</button>
      </div>
    `;
  }

  function staffAlertActions(alert) {
    const options = optionTags(state.lookups?.alertStatusOptions || [], alert.status, value => titleCase(value));
    return `
      <div class="d-flex gap-2">
        <select class="form-select form-select-sm" data-action="staff-alert-status" data-id="${alert.id}">${options}</select>
        <button class="btn btn-outline-success btn-sm" data-action="save-staff-alert" data-id="${alert.id}">Save</button>
      </div>
    `;
  }

  function validationActions(item) {
    const options = optionTags(state.lookups?.validationReviewStatusOptions || [], item.reviewStatus, value => titleCase(value));
    return `
      <div class="d-grid gap-2">
        <select class="form-select form-select-sm" data-action="validation-status" data-id="${item.id}">${options}</select>
        <input class="form-control form-control-sm" data-action="validation-notes" data-id="${item.id}" value="${escapeHtml(item.reviewNotes || '')}" placeholder="Review notes" />
        <div class="d-flex gap-2">
          <button class="btn btn-outline-success btn-sm" data-action="save-validation" data-id="${item.id}">Save</button>
          <button class="btn btn-outline-danger btn-sm" data-action="delete-validation" data-id="${item.id}">Delete</button>
        </div>
      </div>
    `;
  }

  async function mountPage(route, data) {
    switch (route) {
      case 'dashboard': mountDashboard(data); break;
      case 'users': mountUsersPage(data); break;
      case 'bins': mountBinsPage(data); break;
      case 'tasks': mountTasksPage(data); break;
      case 'alerts': mountAlertsPage(data); break;
      case 'reports': mountReportsPage(data); break;
      case 'validations': await mountValidationsPage(data); break;
      case 'profile': mountProfilePage(); break;
      default: break;
    }
  }

  function mountPageEnhancements(route, data, dataTables) {
    void route;
    void data;
    void dataTables;
  }

  function mountDashboard(data) {
    const taskSummary = summarizeByKey(data.recentTasks || [], 'status');
    const validationSummary = summarizeByKey(data.recentValidations || [], 'match');

    mountChart(
      'dashboard-task-chart',
      'bar',
      Object.keys(taskSummary),
      Object.values(taskSummary),
      'Tasks',
      { max: undefined, palette: 'forest' }
    );
    mountChart(
      'dashboard-validation-chart',
      'doughnut',
      Object.keys(validationSummary),
      Object.values(validationSummary),
      'Validations',
      { showLegend: true, palette: 'copper', cutout: '56%' }
    );

    document.querySelectorAll('[data-route-jump]').forEach(button => {
      button.addEventListener('click', async () => {
        state.route = button.dataset.routeJump;
        await renderShell();
      });
    });
  }

  function bindFormSubmit(formId, onSubmit) {
    const form = document.getElementById(formId);
    if (form) form.addEventListener('submit', onSubmit);
  }

  function bindResetButton(buttonId, formId, feedbackId = null) {
    const button = document.getElementById(buttonId);
    const form = document.getElementById(formId);
    if (!button || !form) return;
    button.addEventListener('click', () => {
      form.reset();
      const idField = form.elements.namedItem('id');
      if (idField) idField.value = '';
      if (feedbackId) clearInlineFeedback(feedbackId);
    });
  }

  function setFormValues(formId, item) {
    const form = document.getElementById(formId);
    if (!form) return;
    Object.entries(item).forEach(([key, value]) => {
      const field = form.elements.namedItem(key);
      if (field) field.value = value ?? '';
    });
  }

  function startEdit(formId, feedbackId, item, label) {
    setFormValues(formId, item);
    showActionInfo(feedbackId, `Editing ${label}. Update the fields and click save to apply the changes.`);
    document.getElementById(formId)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  async function reloadCurrentPage(routeOverride = null) {
    if (routeOverride) state.route = routeOverride;
    destroyCharts();
    destroyDataTables();
    stopSensorPolling();
    await refreshLookups();
    state.pageData = await loadPageData(state.route);
    el.contentArea.innerHTML = renderPageHtml(state.route, state.pageData);
    await mountPage(state.route, state.pageData);
    const dataTables = initializeDataTables();
    mountPageEnhancements(state.route, state.pageData, dataTables);
  }

  async function mountUsersPage(users) {
    bindFormSubmit('user-form', async event => {
      event.preventDefault();
      clearInlineFeedback('user-feedback');
      const payload = Object.fromEntries(new FormData(event.target).entries());
      const id = payload.id;
      delete payload.id;
      try {
        await api(id ? `/api/users/${id}` : '/api/users', { method: id ? 'PUT' : 'POST', body: payload });
        await reloadCurrentPage('users');
        showActionSuccess('user-feedback', `User ${id ? 'updated' : 'created'} successfully.`);
      } catch (error) {
        showActionError('user-feedback', error, 'Unable to save the user.');
      }
    });
    bindResetButton('user-form-reset', 'user-form', 'user-feedback');
    users.forEach(user => {
      document.querySelector(`[data-action="edit-user"][data-id="${user.id}"]`)?.addEventListener('click', () => startEdit('user-form', 'user-feedback', user, user.fullName));
      document.querySelector(`[data-action="delete-user"][data-id="${user.id}"]`)?.addEventListener('click', async () => {
        if (!window.confirm(`Delete user "${user.fullName}"? This action cannot be undone.`)) return;
        clearInlineFeedback('user-feedback');
        try {
          await api(`/api/users/${user.id}`, { method: 'DELETE' });
          await reloadCurrentPage('users');
          showActionSuccess('user-feedback', 'User deleted successfully.');
        } catch (error) {
          showActionError('user-feedback', error, 'Unable to delete the user.');
        }
      });
    });
  }

  async function mountBinsPage(bins) {
    if (state.user.role !== 'staff') {
      bindFormSubmit('bin-form', async event => {
        event.preventDefault();
        clearInlineFeedback('bin-feedback');
        const payload = Object.fromEntries(new FormData(event.target).entries());
        const id = payload.id;
        delete payload.id;
        try {
          await api(id ? `/api/bins/${id}` : '/api/bins', { method: id ? 'PUT' : 'POST', body: payload });
          await reloadCurrentPage('bins');
          showActionSuccess('bin-feedback', `Bin ${id ? 'updated' : 'created'} successfully.`);
        } catch (error) {
          showActionError('bin-feedback', error, 'Unable to save the bin.');
        }
      });
      bindResetButton('bin-form-reset', 'bin-form', 'bin-feedback');
      bins.forEach(bin => {
        document.querySelector(`[data-action="edit-bin"][data-id="${bin.id}"]`)?.addEventListener('click', () => startEdit('bin-form', 'bin-feedback', bin, bin.binCode));
        document.querySelector(`[data-action="delete-bin"][data-id="${bin.id}"]`)?.addEventListener('click', async () => {
          if (!window.confirm(`Delete bin "${bin.binCode}"? This action cannot be undone.`)) return;
          clearInlineFeedback('bin-feedback');
          try {
            await api(`/api/bins/${bin.id}`, { method: 'DELETE' });
            await reloadCurrentPage('bins');
            showActionSuccess('bin-feedback', 'Bin deleted successfully.');
          } catch (error) {
            showActionError('bin-feedback', error, 'Unable to delete the bin.');
          }
        });
      });
    }
  }

  async function mountTasksPage(tasks) {
    if (state.user.role === 'staff') {
      tasks.forEach(task => {
        document.querySelector(`[data-action="save-staff-task"][data-id="${task.id}"]`)?.addEventListener('click', async () => {
          clearInlineFeedback('task-feedback');
          const status = document.querySelector(`[data-action="staff-task-status"][data-id="${task.id}"]`)?.value || task.status;
          try {
            await api(`/api/tasks/${task.id}`, { method: 'PUT', body: { status } });
            await reloadCurrentPage('tasks');
            showActionSuccess('task-feedback', `Task "${task.title}" updated successfully.`);
          } catch (error) {
            showActionError('task-feedback', error, 'Unable to update the task.');
          }
        });
      });
      return;
    }

    bindFormSubmit('task-form', async event => {
      event.preventDefault();
      clearInlineFeedback('task-feedback');
      const payload = Object.fromEntries(new FormData(event.target).entries());
      const id = payload.id;
      delete payload.id;
      try {
        await api(id ? `/api/tasks/${id}` : '/api/tasks', { method: id ? 'PUT' : 'POST', body: payload });
        await reloadCurrentPage('tasks');
        showActionSuccess('task-feedback', `Task ${id ? 'updated' : 'created'} successfully.`);
      } catch (error) {
        showActionError('task-feedback', error, 'Unable to save the task.');
      }
    });
    bindResetButton('task-form-reset', 'task-form', 'task-feedback');
    tasks.forEach(task => {
      document.querySelector(`[data-action="edit-task"][data-id="${task.id}"]`)?.addEventListener('click', () => startEdit('task-form', 'task-feedback', task, task.title));
      document.querySelector(`[data-action="delete-task"][data-id="${task.id}"]`)?.addEventListener('click', async () => {
        if (!window.confirm(`Delete task "${task.title}"? This action cannot be undone.`)) return;
        clearInlineFeedback('task-feedback');
        try {
          await api(`/api/tasks/${task.id}`, { method: 'DELETE' });
          await reloadCurrentPage('tasks');
          showActionSuccess('task-feedback', 'Task deleted successfully.');
        } catch (error) {
          showActionError('task-feedback', error, 'Unable to delete the task.');
        }
      });
    });
  }

  async function mountAlertsPage(alerts) {
    if (state.user.role === 'staff') {
      alerts.forEach(alert => {
        document.querySelector(`[data-action="save-staff-alert"][data-id="${alert.id}"]`)?.addEventListener('click', async () => {
          clearInlineFeedback('alert-feedback');
          const status = document.querySelector(`[data-action="staff-alert-status"][data-id="${alert.id}"]`)?.value || alert.status;
          try {
            await api(`/api/alerts/${alert.id}`, { method: 'PUT', body: { status } });
            await reloadCurrentPage('alerts');
            showActionSuccess('alert-feedback', `Alert "${alert.title}" updated successfully.`);
          } catch (error) {
            showActionError('alert-feedback', error, 'Unable to update the alert.');
          }
        });
      });
      return;
    }

    bindFormSubmit('alert-form', async event => {
      event.preventDefault();
      clearInlineFeedback('alert-feedback');
      const payload = Object.fromEntries(new FormData(event.target).entries());
      const id = payload.id;
      delete payload.id;
      try {
        await api(id ? `/api/alerts/${id}` : '/api/alerts', { method: id ? 'PUT' : 'POST', body: payload });
        await reloadCurrentPage('alerts');
        showActionSuccess('alert-feedback', `Alert ${id ? 'updated' : 'created'} successfully.`);
      } catch (error) {
        showActionError('alert-feedback', error, 'Unable to save the alert.');
      }
    });
    bindResetButton('alert-form-reset', 'alert-form', 'alert-feedback');
    alerts.forEach(alert => {
      document.querySelector(`[data-action="edit-alert"][data-id="${alert.id}"]`)?.addEventListener('click', () => startEdit('alert-form', 'alert-feedback', alert, alert.title));
      document.querySelector(`[data-action="delete-alert"][data-id="${alert.id}"]`)?.addEventListener('click', async () => {
        if (!window.confirm(`Delete alert "${alert.title}"? This action cannot be undone.`)) return;
        clearInlineFeedback('alert-feedback');
        try {
          await api(`/api/alerts/${alert.id}`, { method: 'DELETE' });
          await reloadCurrentPage('alerts');
          showActionSuccess('alert-feedback', 'Alert deleted successfully.');
        } catch (error) {
          showActionError('alert-feedback', error, 'Unable to delete the alert.');
        }
      });
    });
  }

  async function mountReportsPage(_reports) {
    const fromInput = document.getElementById('report-filter-from');
    const toInput = document.getElementById('report-filter-to');
    const clearButton = document.getElementById('report-filter-clear');

    const applyFilter = async () => {
      state.reportDateFilter = {
        from: fromInput?.value || '',
        to: toInput?.value || ''
      };
      await reloadCurrentPage('reports');
    };

    fromInput?.addEventListener('change', applyFilter);
    toInput?.addEventListener('change', applyFilter);

    clearButton?.addEventListener('click', async () => {
      state.reportDateFilter = { from: '', to: '' };
      if (fromInput) fromInput.value = '';
      if (toInput) toInput.value = '';
      await reloadCurrentPage('reports');
    });
  }

  async function mountValidationsPage(validations) {
    bindFormSubmit('validation-form', async event => {
      event.preventDefault();
      clearInlineFeedback('validation-feedback');
      const formData = new FormData(event.target);
      try {
        const result = await api('/api/validate', { method: 'POST', body: formData });
        state.validationResult = result;
        await reloadCurrentPage('validations');
        showActionSuccess('validation-feedback', 'Validation saved successfully.');
      } catch (error) {
        showActionError('validation-feedback', error, 'Unable to run the validation.');
      }
    });

    await startSensorPolling();

    validations.forEach(item => {
      document.querySelector(`[data-action="save-validation"][data-id="${item.id}"]`)?.addEventListener('click', async () => {
        clearInlineFeedback('validation-feedback');
        const reviewStatus = document.querySelector(`[data-action="validation-status"][data-id="${item.id}"]`)?.value || item.reviewStatus;
        const reviewNotes = document.querySelector(`[data-action="validation-notes"][data-id="${item.id}"]`)?.value || '';
        try {
          await api(`/api/validations/${item.id}`, { method: 'PUT', body: { reviewStatus, reviewNotes } });
          await reloadCurrentPage('validations');
          showActionSuccess('validation-feedback', 'Validation review updated successfully.');
        } catch (error) {
          showActionError('validation-feedback', error, 'Unable to update the validation review.');
        }
      });
      document.querySelector(`[data-action="delete-validation"][data-id="${item.id}"]`)?.addEventListener('click', async () => {
        if (!window.confirm('Delete this validation record? This action cannot be undone.')) return;
        clearInlineFeedback('validation-feedback');
        try {
          await api(`/api/validations/${item.id}`, { method: 'DELETE' });
          await reloadCurrentPage('validations');
          showActionSuccess('validation-feedback', 'Validation deleted successfully.');
        } catch (error) {
          showActionError('validation-feedback', error, 'Unable to delete the validation record.');
        }
      });
    });
  }

  function mountProfilePage() {
    bindFormSubmit('profile-form', async event => {
      event.preventDefault();
      clearInlineFeedback('profile-feedback');
      const payload = Object.fromEntries(new FormData(event.target).entries());
      try {
        const response = await api('/api/profile', { method: 'PUT', body: payload });
        state.user = response.user;
        await renderShell();
        showActionSuccess('profile-feedback', 'Profile updated successfully.');
      } catch (error) {
        showActionError('profile-feedback', error, 'Unable to update your profile.');
      }
    });
  }

  async function startSensorPolling() {
    stopSensorPolling();
    await refreshSensorCard();
    state.sensorTimer = setInterval(refreshSensorCard, 2000);
  }

  function stopSensorPolling() {
    if (state.sensorTimer) {
      clearInterval(state.sensorTimer);
      state.sensorTimer = null;
    }
  }

  async function refreshSensorCard() {
    const sensorField = document.getElementById('sensor-level-output');
    const sourceField = document.getElementById('sensor-source-output');
    if (!sensorField || !sourceField) return;

    try {
      const sensor = await api('/api/sensor/latest');
      const distance = typeof sensor.distance_cm === 'number' ? `${sensor.distance_cm.toFixed(2)} cm` : 'No reading';
      const hasReading = typeof sensor.distance_cm === 'number' || typeof sensor.distance_inch === 'number';
      sensorField.value = hasReading
        ? `${String(sensor.sensor_level || 'unknown').toUpperCase()} (${distance})`
        : 'Waiting for live sensor reading';
      sourceField.value = `${String(sensor.source || 'manual').toUpperCase()} | ${sensor.status || 'You can still enter a manual distance.'}`;
    } catch (error) {
      sensorField.value = 'Sensor API error';
      sourceField.value = error.message;
    }
  }

  function formatDateTime(value) {
    if (!value) return '-';
    return String(value).replace('T', ' ');
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }

  function titleCase(str) {
    return String(str || '').replace(/\b\w/g, char => char.toUpperCase());
  }

  init();
})();

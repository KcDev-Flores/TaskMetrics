// ==============================================================================
// TaskMetrics - Lógica de Navegación, Dashboard, Tablero y Rendimiento
// ==============================================================================

let currentMetrics = null;
let currentSprints = [];
let currentProgrammers = [];
let editingSprintNumber = null;
let activeTab = "dashboard";
let currentSearchQuery = "";
let currentSortKey = "percentage_desc";

// -----------------------------------------------------------------------------
// Control de Sesión y Supabase Auth
// -----------------------------------------------------------------------------
let currentUser = null;
let authMode = "login"; // 'login' o 'register'

function getStoredToken() {
  return localStorage.getItem("tm_access_token") || "";
}

function setStoredToken(token) {
  if (token) {
    localStorage.setItem("tm_access_token", token);
  } else {
    localStorage.removeItem("tm_access_token");
  }
}

function getStoredRefreshToken() {
  return localStorage.getItem("tm_refresh_token") || "";
}

function setStoredRefreshToken(token) {
  if (token) {
    localStorage.setItem("tm_refresh_token", token);
  } else {
    localStorage.removeItem("tm_refresh_token");
  }
}

function escapeHtml(str) {
  if (str === null || str === undefined) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

async function authFetch(url, options = {}) {
  const token = getStoredToken();
  const headers = { ...(options.headers || {}) };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  options.headers = headers;

  const res = await fetch(url, options);

  if (res.status === 401) {
    // Sesión expirada o no autorizada
    setStoredToken("");
    setStoredRefreshToken("");
    currentUser = null;
    updateAuthUI();
    showToast("Tu sesión ha expirado o no está autorizada. Por favor inicia sesión.", "error");
    throw new Error("Sesión no autorizada o expirada.");
  }

  return res;
}

async function checkAuthStatus() {
  const token = getStoredToken();
  if (!token) {
    updateAuthUI();
    return false;
  }
  try {
    const res = await fetch("/api/auth/me", {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (res.ok) {
      const data = await res.json();
      currentUser = data.user;
      updateAuthUI();
      return true;
    } else {
      setStoredToken("");
      setStoredRefreshToken("");
      currentUser = null;
      updateAuthUI();
      return false;
    }
  } catch (e) {
    updateAuthUI();
    return false;
  }
}

function updateAuthUI() {
  const loginScreen = document.getElementById("login-view-screen");
  const mainLayout = document.getElementById("app-main-layout");
  const userBadge = document.getElementById("user-badge");
  const roleBadge = document.getElementById("user-role-badge");
  const nameDisplay = document.getElementById("user-name-display");
  const tabUsuarios = document.getElementById("tab-btn-usuarios");

  if (currentUser) {
    if (loginScreen) loginScreen.classList.add("hidden");
    if (mainLayout) {
      mainLayout.classList.remove("hidden");
      mainLayout.classList.add("flex");
    }
    if (userBadge) {
      userBadge.classList.remove("hidden");
      userBadge.classList.add("flex");
    }
    if (nameDisplay) {
      const displayName = currentUser.name || currentUser.email.split("@")[0];
      nameDisplay.textContent = displayName;
      nameDisplay.title = `${displayName} (${currentUser.email})`;
    }
    if (roleBadge) {
      if (currentUser.role === "admin") {
        roleBadge.textContent = "👑 Administrador";
        roleBadge.className = "px-1.5 sm:px-2 py-0.5 rounded-md font-semibold text-[10px] bg-amber-500/20 text-amber-300 border border-amber-500/30";
      } else {
        roleBadge.textContent = "⭐ Líder";
        roleBadge.className = "px-1.5 sm:px-2 py-0.5 rounded-md font-semibold text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      }
    }
    if (tabUsuarios) {
      if (currentUser.role === "admin") {
        tabUsuarios.classList.remove("hidden");
      } else {
        tabUsuarios.classList.add("hidden");
        if (activeTab === "usuarios") {
          switchTab("dashboard");
        }
      }
    }
  } else {
    if (loginScreen) loginScreen.classList.remove("hidden");
    if (mainLayout) {
      mainLayout.classList.add("hidden");
      mainLayout.classList.remove("flex");
    }
    if (userBadge) {
      userBadge.classList.add("hidden");
      userBadge.classList.remove("flex");
    }
    if (tabUsuarios) {
      tabUsuarios.classList.add("hidden");
    }
  }
}

async function submitCleanLogin() {
  const emailInput = document.getElementById("login-input-email");
  const passwordInput = document.getElementById("login-input-password");
  const errorAlert = document.getElementById("login-error-alert");
  const errorText = document.getElementById("login-error-text");
  const submitBtn = document.getElementById("btn-login-submit");
  const submitText = document.getElementById("btn-login-text");

  const email = emailInput?.value.trim();
  const password = passwordInput?.value;

  if (!email || !password) {
    if (errorText) errorText.textContent = "Por favor ingresa tu correo y contraseña.";
    errorAlert?.classList.remove("hidden");
    return;
  }

  try {
    if (submitBtn) submitBtn.disabled = true;
    if (submitText) submitText.textContent = "Ingresando...";
    errorAlert?.classList.add("hidden");

    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Error en el inicio de sesión.");
    }

    setStoredToken(data.access_token);
    if (data.refresh_token) setStoredRefreshToken(data.refresh_token);
    currentUser = data.user;

    if (passwordInput) passwordInput.value = "";

    updateAuthUI();
    showToast(`¡Bienvenido/a, ${currentUser.name || currentUser.email}!`);
    loadDashboard();
  } catch (err) {
    if (errorText) errorText.textContent = err.message || "Error al iniciar sesión.";
    errorAlert?.classList.remove("hidden");
  } finally {
    if (submitBtn) submitBtn.disabled = false;
    if (submitText) submitText.textContent = "Iniciar Sesión";
  }
}

function openAuthModal(mode = "login") {
  authMode = mode;
  switchAuthMode(mode);
  openModal("modal-auth");
}

function switchAuthMode(mode) {
  authMode = mode;
  const isLogin = mode === "login";
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const confirmField = document.getElementById("auth-field-confirm-password");
  const submitText = document.getElementById("btn-auth-text");
  const toggleCaption = document.getElementById("auth-toggle-caption");
  const errorAlert = document.getElementById("auth-error-alert");

  if (errorAlert) errorAlert.classList.add("hidden");

  if (isLogin) {
    if (tabLogin) tabLogin.className = "flex-1 py-1.5 text-xs font-semibold rounded-lg transition text-white bg-slate-800 shadow-sm";
    if (tabRegister) tabRegister.className = "flex-1 py-1.5 text-xs font-semibold rounded-lg transition text-slate-400 hover:text-slate-200";
    confirmField?.classList.add("hidden");
    if (submitText) submitText.textContent = "Iniciar Sesión";
    if (toggleCaption) {
      toggleCaption.innerHTML = '¿No tienes una cuenta aún? <button type="button" onclick="switchAuthMode(\'register\')" class="text-emerald-400 hover:underline font-medium">Regístrate</button>';
    }
  } else {
    if (tabRegister) tabRegister.className = "flex-1 py-1.5 text-xs font-semibold rounded-lg transition text-white bg-slate-800 shadow-sm";
    if (tabLogin) tabLogin.className = "flex-1 py-1.5 text-xs font-semibold rounded-lg transition text-slate-400 hover:text-slate-200";
    confirmField?.classList.remove("hidden");
    if (submitText) submitText.textContent = "Crear Cuenta en Supabase";
    if (toggleCaption) {
      toggleCaption.innerHTML = '¿Ya tienes una cuenta? <button type="button" onclick="switchAuthMode(\'login\')" class="text-emerald-400 hover:underline font-medium">Inicia sesión</button>';
    }
  }
}

async function submitAuth() {
  const email = document.getElementById("auth-input-email")?.value.trim();
  const password = document.getElementById("auth-input-password")?.value;
  const confirmPassword = document.getElementById("auth-input-confirm-password")?.value;
  const errorAlert = document.getElementById("auth-error-alert");
  const submitBtn = document.getElementById("btn-auth-submit");

  if (!email || !password) {
    if (errorAlert) {
      errorAlert.textContent = "Por favor ingresa correo y contraseña.";
      errorAlert.classList.remove("hidden");
    }
    return;
  }

  if (authMode === "register" && password !== confirmPassword) {
    if (errorAlert) {
      errorAlert.textContent = "Las contraseñas no coinciden.";
      errorAlert.classList.remove("hidden");
    }
    return;
  }

  try {
    if (submitBtn) submitBtn.disabled = true;
    if (errorAlert) errorAlert.classList.add("hidden");

    const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Error en la autenticación");
    }

    if (authMode === "register") {
      showToast("¡Cuenta registrada con éxito!");
      if (data.session && data.session.access_token) {
        setStoredToken(data.session.access_token);
        if (data.session.refresh_token) setStoredRefreshToken(data.session.refresh_token);
        currentUser = data.user;
      } else {
        // Intentar login automático
        const loginRes = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password })
        });
        const loginData = await loginRes.json();
        if (loginRes.ok) {
          setStoredToken(loginData.access_token);
          if (loginData.refresh_token) setStoredRefreshToken(loginData.refresh_token);
          currentUser = loginData.user;
        } else {
          showToast("Cuenta creada. Por favor inicia sesión.", "success");
          switchAuthMode("login");
          return;
        }
      }
    } else {
      setStoredToken(data.access_token);
      if (data.refresh_token) setStoredRefreshToken(data.refresh_token);
      currentUser = data.user;
      showToast(`¡Sesión iniciada como ${currentUser.email}!`);
    }

    updateAuthUI();
    closeModal("modal-auth");
    loadDashboard();
  } catch (err) {
    if (errorAlert) {
      errorAlert.textContent = err.message;
      errorAlert.classList.remove("hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function logout() {
  try {
    await authFetch("/api/auth/logout", { method: "POST" });
  } catch (e) {
    // Ignorar si el token ya expiró
  }
  setStoredToken("");
  setStoredRefreshToken("");
  currentUser = null;
  updateAuthUI();
  showToast("Sesión cerrada correctamente.");
}

document.addEventListener("DOMContentLoaded", async () => {
  // Inicializar pestaña por hash de URL (si existe)
  const initialHash = window.location.hash.replace("#", "");
  if (["dashboard", "tablero", "rendimiento", "usuarios"].includes(initialHash)) {
    activeTab = initialHash;
  }
  applyActiveTabUI();

  // Verificar autenticación con Supabase
  const isAuth = await checkAuthStatus();
  if (isAuth) {
    if (activeTab === "usuarios" && currentUser?.role === "admin") {
      loadUsersList();
    } else {
      loadDashboard();
    }
  }

  // Cerrar menú desplegable al hacer clic fuera
  document.addEventListener("click", (e) => {
    const wrapper = document.getElementById("actions-dropdown-wrapper");
    const menu = document.getElementById("actions-menu");
    if (wrapper && !wrapper.contains(e.target) && menu && !menu.classList.contains("hidden")) {
      menu.classList.add("hidden");
    }
  });
});

// -----------------------------------------------------------------------------
// Control de Pestañas de Navegación
// -----------------------------------------------------------------------------
function switchTab(tabName) {
  if (tabName === "usuarios" && currentUser?.role !== "admin") {
    showToast("Acceso denegado: solo el Administrador puede gestionar usuarios.", "error");
    return;
  }
  activeTab = tabName;
  window.location.hash = tabName;
  applyActiveTabUI();

  if (tabName === "usuarios") {
    loadUsersList();
  } else if (tabName === "dashboard") {
    if (!currentMetrics) loadDashboard();
  }
}

function applyActiveTabUI() {
  const tabs = ["dashboard", "tablero", "rendimiento", "usuarios"];
  tabs.forEach(t => {
    const view = document.getElementById(`view-${t}`);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (view && btn) {
      if (t === activeTab) {
        view.classList.remove("hidden");
        btn.className = "nav-tab px-3 sm:px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-white bg-slate-800 shadow-sm shrink-0";
      } else {
        view.classList.add("hidden");
        btn.className = "nav-tab px-3 sm:px-4 py-1.5 rounded-lg text-xs font-semibold transition flex items-center gap-1.5 text-slate-400 hover:text-slate-200 shrink-0";
      }
    }
  });
}

// -----------------------------------------------------------------------------
// Notificaciones Toast
// -----------------------------------------------------------------------------
function showToast(message, type = "success") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  const isError = type === "error";

  toast.className = `flex items-center gap-2 px-4 py-3 rounded-xl text-sm shadow-xl transition transform duration-300 translate-y-2 border ${
    isError 
      ? "bg-rose-950/95 border-rose-800 text-rose-200" 
      : "bg-emerald-950/95 border-emerald-800 text-emerald-200"
  }`;

  toast.innerHTML = `
    <span>${isError ? '⚠️' : '✅'}</span>
    <span class="flex-1 font-medium">${message}</span>
    <button onclick="this.parentElement.remove()" class="text-xs opacity-70 hover:opacity-100">&times;</button>
  `;

  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// -----------------------------------------------------------------------------
// Menú Desplegable Acciones y Modales
// -----------------------------------------------------------------------------
function toggleActionsMenu() {
  const menu = document.getElementById("actions-menu");
  if (menu) menu.classList.toggle("hidden");
}

function closeActionsMenu() {
  const menu = document.getElementById("actions-menu");
  if (menu) menu.classList.add("hidden");
}

function openModal(id) {
  closeActionsMenu();
  const m = document.getElementById(id);
  if (m) m.classList.remove("hidden");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add("hidden");
}

// -----------------------------------------------------------------------------
// Carga Principal de Datos
// -----------------------------------------------------------------------------
async function loadDashboard() {
  const upToVal = document.getElementById("filter-up-to")?.value;
  let metricsUrl = "/api/metrics";
  if (upToVal) metricsUrl += `?up_to=${upToVal}`;

  try {
    const [resMetrics, resSprints, resProgs] = await Promise.all([
      authFetch(metricsUrl),
      authFetch("/api/sprints"),
      authFetch("/api/programmers")
    ]);

    if (!resMetrics.ok) throw new Error("Error al obtener métricas");
    currentMetrics = await resMetrics.json();
    currentSprints = resSprints.ok ? await resSprints.json() : [];
    currentProgrammers = resProgs.ok ? await resProgs.json() : [];

    // Renderizar las 3 Vistas
    renderDashboardView(currentMetrics);
    renderTableroView(currentMetrics);
    renderRendimientoView(currentMetrics);
    updateFilterOptions(currentMetrics.sprints);
  } catch (err) {
    showToast(err.message, "error");
  }
}





// -----------------------------------------------------------------------------
// VISTA 1: DASHBOARD
// -----------------------------------------------------------------------------
function renderDashboardView(data) {
  const circle = document.getElementById("circle-global-progress");
  const pctText = document.getElementById("circle-global-pct");
  const compStat = document.getElementById("stat-completed-tasks");
  const assgStat = document.getElementById("stat-assigned-tasks");

  const rate = data.overall_completion_rate || 0;
  const completed = data.team_total_tasks || 0;
  const assigned = data.team_total_assigned || completed;

  pctText.textContent = `${rate.toFixed(1)}%`;
  compStat.textContent = completed;
  assgStat.textContent = assigned;

  const strokeVal = Math.min(Math.max(rate, 0), 100);
  circle.setAttribute("stroke-dasharray", `${strokeVal}, 100`);

  document.getElementById("kpi-sprints-count").textContent = data.sprints.length;
  document.getElementById("kpi-devs-count").textContent = data.programmers.length;

  const topContainer = document.getElementById("dashboard-top-contributors");
  topContainer.innerHTML = "";

  if (!data.matrix || data.matrix.length === 0) {
    topContainer.innerHTML = `
      <div class="col-span-full py-8 text-center text-xs text-slate-500">
        No hay datos registrados aún. Usa el botón "⚙️ Acciones" en el Tablero para registrar integrantes y sprints.
      </div>
    `;
    return;
  }

  const sorted = [...data.matrix].sort((a, b) => b.percentage - a.percentage).slice(0, 4);

  sorted.forEach((m, idx) => {
    const card = document.createElement("div");
    card.className = "bg-slate-950/70 border border-slate-800 rounded-xl p-4 flex items-center gap-3 cursor-pointer hover:border-emerald-500/40 transition";
    card.onclick = () => {
      switchTab('rendimiento');
      openDevHistoryModal(m.programmer_name);
    };
    card.innerHTML = `
      <div class="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold flex items-center justify-center text-sm">
        #${idx + 1}
      </div>
      <div class="flex-1 truncate">
        <span class="text-xs font-semibold text-white truncate block">${m.programmer_name}</span>
        <span class="text-[11px] text-slate-400 block">${m.total_accumulated} tareas cerradas</span>
      </div>
      <div class="text-right">
        <span class="text-sm font-bold text-emerald-400 font-mono">${m.percentage.toFixed(2)}%</span>
      </div>
    `;
    topContainer.appendChild(card);
  });
}

// -----------------------------------------------------------------------------
// VISTA 2: TABLERO (Control de Rendimiento y Matriz)
// -----------------------------------------------------------------------------
function renderTableroView(data) {
  renderMatrixTable(data);
  renderSprintsAccordion();
}

function renderMatrixTable(data) {
  const headersRow = document.getElementById("matrix-headers");
  const tbody = document.getElementById("matrix-body");
  const tfoot = document.getElementById("matrix-foot");

  // Reconstruir Encabezados
  headersRow.innerHTML = `
    <th class="py-3.5 px-4 font-semibold text-slate-300 bg-slate-950 min-w-[160px]">Integrante</th>
  `;

  data.sprints.forEach((s) => {
    const sName = data.sprint_names?.[s] || `Sprint ${s}`;
    const th = document.createElement("th");
    th.className = "py-3.5 px-3 text-center font-semibold text-slate-300 bg-slate-950 min-w-[100px]";
    th.innerHTML = `
      <div class="flex flex-col items-center">
        <span>Sprint ${s}</span>
        <span class="text-[10px] text-slate-500 font-normal truncate max-w-[100px]" title="${sName}">${sName}</span>
      </div>
    `;
    headersRow.appendChild(th);
  });

  // Columnas fijas finales (con ancho y alineación exacta)
  headersRow.innerHTML += `
    <th class="py-3.5 px-4 text-center font-semibold text-slate-300 bg-slate-950 w-36 whitespace-nowrap">Total Acumulado</th>
    <th class="py-3.5 px-4 text-left font-semibold text-slate-300 min-w-[220px] bg-slate-950">Participación de Ingresos (%)</th>
    <th class="py-3.5 px-4 text-center font-semibold text-slate-400 bg-slate-950 w-28 whitespace-nowrap">Eficacia</th>
  `;

  // Reconstruir Filas
  tbody.innerHTML = "";
  if (!data.matrix || data.matrix.length === 0) {
    const colSpan = data.sprints.length + 4;
    tbody.innerHTML = `
      <tr>
        <td colspan="${colSpan}" class="py-12 text-center text-slate-500 text-xs">
          No hay datos registrados aún. Usa el botón <strong>"⚙️ Acciones"</strong> para registrar integrantes y sprints.
        </td>
      </tr>
    `;
    tfoot.innerHTML = "";
    return;
  }

  data.matrix.forEach((item) => {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-900/40 transition";

    let cells = `
      <td class="py-3 px-4 font-medium text-slate-200 min-w-[160px]">
        <span class="cursor-pointer hover:text-emerald-400 transition" onclick="switchTab('rendimiento'); openDevHistoryModal('${item.programmer_name}')" title="Ver historial de ${item.programmer_name}">
          ${item.programmer_name}
        </span>
      </td>
    `;

    data.sprints.forEach((s) => {
      const count = item.sprint_tasks[s] ?? 0;
      cells += `
        <td class="py-3 px-3 text-center text-slate-300 font-mono text-xs min-w-[100px]">
          ${count}
        </td>
      `;
    });

    const pct = item.percentage.toFixed(4);
    cells += `
      <!-- Total Acumulado perfectamente centrado y alineado con el encabezado -->
      <td class="py-3 px-4 text-center font-bold text-white font-mono w-36">
        ${item.total_accumulated}
      </td>
      <td class="py-3 px-4 min-w-[220px]">
        <div class="flex items-center gap-3">
          <div class="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
            <div class="bg-emerald-500 h-2 rounded-full transition-all duration-500" style="width: ${Math.min(item.percentage, 100)}%"></div>
          </div>
          <span class="font-mono text-xs font-semibold text-emerald-400 w-16 text-right">${pct}%</span>
        </div>
      </td>
      <td class="py-3 px-4 text-center font-mono text-xs text-slate-300 w-28">
        ${item.completion_rate.toFixed(1)}%
      </td>
    `;

    tr.innerHTML = cells;
    tbody.appendChild(tr);
  });

  // Reconstruir Pie
  let foot = `
    <tr>
      <td class="py-3.5 px-4 text-emerald-400 font-bold uppercase tracking-wider text-xs min-w-[160px]">TOTAL EQUIPO</td>
  `;

  data.sprints.forEach((s) => {
    const sTotal = data.sprint_totals[s] ?? 0;
    foot += `
      <td class="py-3 px-3 text-center text-slate-200 font-bold font-mono text-xs min-w-[100px]">
        ${sTotal}
      </td>
    `;
  });

  foot += `
      <!-- Total Acumulado del equipo perfectamente centrado y alineado -->
      <td class="py-3.5 px-4 text-center text-emerald-400 font-bold font-mono w-36">
        ${data.team_total_tasks}
      </td>
      <td class="py-3.5 px-4 min-w-[220px]">
        <div class="flex items-center gap-3">
          <div class="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
            <div class="bg-emerald-400 h-2 rounded-full" style="width: 100%"></div>
          </div>
          <span class="font-mono text-xs font-bold text-emerald-400 w-16 text-right">100.0000%</span>
        </div>
      </td>
      <td class="py-3.5 px-4 text-center font-mono text-xs font-bold text-emerald-400 w-28">
        ${data.overall_completion_rate.toFixed(1)}%
      </td>
    </tr>
  `;
  tfoot.innerHTML = foot;
}

async function renderSprintsAccordion() {
  const container = document.getElementById("sprints-details-list");
  container.innerHTML = "";

  if (!currentSprints || currentSprints.length === 0) {
    container.innerHTML = `
      <p class="text-xs text-slate-500 text-center py-6">
        No se han registrado sprints todavía.
      </p>
    `;
    return;
  }

  for (const s of currentSprints) {
    const card = document.createElement("div");
    card.className = "bg-slate-950/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm";

    card.innerHTML = `
      <div class="p-4 flex items-center justify-between cursor-pointer hover:bg-slate-900/50 transition" onclick="toggleSprintDetails(${s.sprint_number})">
        <div class="flex items-center gap-3">
          <span class="px-2.5 py-1 bg-slate-800 text-emerald-400 text-xs font-bold rounded-lg border border-slate-700">
            Sprint ${s.sprint_number}
          </span>
          <span class="text-sm font-semibold text-white">${s.name}</span>
          <span class="text-xs text-slate-500 font-normal">(${s.task_count} tareas)</span>
        </div>
        <div class="flex items-center gap-3">
          <span class="text-xs px-2.5 py-0.5 rounded-full ${s.status === 'completed' ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800' : 'bg-amber-950/80 text-amber-400 border border-amber-800'}">
            ${s.status === 'completed' ? 'Completado' : 'En progreso'}
          </span>
          <span id="chevron-sprint-${s.sprint_number}" class="text-slate-400 text-sm">▼</span>
        </div>
      </div>

      <div id="details-sprint-${s.sprint_number}" class="hidden p-4 border-t border-slate-800/80 bg-slate-900/30">
        <div class="text-xs text-slate-500">Cargando tareas...</div>
      </div>
    `;

    container.appendChild(card);
  }
}

async function toggleSprintDetails(sprintNum) {
  const detailsDiv = document.getElementById(`details-sprint-${sprintNum}`);
  const chevron = document.getElementById(`chevron-sprint-${sprintNum}`);
  if (!detailsDiv) return;

  const isHidden = detailsDiv.classList.contains("hidden");
  if (isHidden) {
    detailsDiv.classList.remove("hidden");
    chevron.textContent = "▲";

    try {
      const res = await authFetch(`/api/sprints/${sprintNum}`);
      if (!res.ok) throw new Error("Error al cargar tareas");
      const data = await res.json();

      if (!data.tasks || data.tasks.length === 0) {
        detailsDiv.innerHTML = `<p class="text-xs text-slate-500">No hay tareas especificadas en este sprint.</p>`;
        return;
      }

      let listHtml = `<div class="space-y-2">`;
      data.tasks.forEach((t) => {
        const assignedBadges = t.assigned_programmers.map(p => `
          <span class="inline-flex items-center px-2 py-0.5 rounded bg-slate-800 text-emerald-300 text-[11px] border border-slate-700">
            👤 ${p}
          </span>
        `).join(" ");

        listHtml += `
          <div class="p-2.5 bg-slate-950/80 rounded-lg border border-slate-800 flex items-center justify-between gap-3">
            <div class="flex items-center gap-2.5 flex-1 truncate">
              <span class="text-xs font-semibold ${t.status === 'completed' ? 'text-white' : 'text-slate-400'}">
                ${t.title}
              </span>
              <span class="text-[10px] px-1.5 py-0.5 rounded ${t.status === 'completed' ? 'bg-emerald-950 text-emerald-400' : 'bg-slate-800 text-slate-400'}">
                ${t.status === 'completed' ? 'Hecha' : 'Pendiente'}
              </span>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap justify-end">
              <span class="text-[11px] text-slate-400 mr-1">Colaboradores:</span>
              ${assignedBadges || '<span class="text-[11px] text-slate-500 italic">Sin asignación</span>'}
            </div>
          </div>
        `;
      });
      listHtml += `</div>`;
      detailsDiv.innerHTML = listHtml;
    } catch (err) {
      detailsDiv.innerHTML = `<p class="text-xs text-rose-400">${err.message}</p>`;
    }
  } else {
    detailsDiv.classList.add("hidden");
    chevron.textContent = "▼";
  }
}

// -----------------------------------------------------------------------------
// VISTA 3: RENDIMIENTO (Desempeño Individual de Todos los Integrantes)
// -----------------------------------------------------------------------------
function renderRendimientoView(data) {
  const container = document.getElementById("rendimiento-cards-container");
  container.innerHTML = "";

  if (!data.matrix || data.matrix.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-16 text-center text-xs text-slate-500">
        No hay datos de integrantes disponibles. Registra integrantes y sprints para ver el rendimiento individual.
      </div>
    `;
    return;
  }

  let items = [...data.matrix];
  if (currentSearchQuery) {
    const q = currentSearchQuery.toLowerCase();
    items = items.filter(m => m.programmer_name.toLowerCase().includes(q));
  }

  if (currentSortKey === "percentage_desc") {
    items.sort((a, b) => b.percentage - a.percentage);
  } else if (currentSortKey === "tasks_desc") {
    items.sort((a, b) => b.total_accumulated - a.total_accumulated);
  } else if (currentSortKey === "efficiency_desc") {
    items.sort((a, b) => b.completion_rate - a.completion_rate);
  } else if (currentSortKey === "name_asc") {
    items.sort((a, b) => a.programmer_name.localeCompare(b.programmer_name));
  }

  if (items.length === 0) {
    container.innerHTML = `
      <div class="col-span-full py-12 text-center text-xs text-slate-500">
        No se encontraron integrantes que coincidan con "${currentSearchQuery}".
      </div>
    `;
    return;
  }

  items.forEach((m) => {
    const card = document.createElement("div");
    card.className = "bg-slate-900/70 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between shadow-sm hover:border-emerald-500/50 hover:bg-slate-900/90 cursor-pointer transition group";
    card.onclick = () => openDevHistoryModal(m.programmer_name);

    const revenuePct = m.percentage.toFixed(2);
    const strokeVal = Math.min(Math.max(m.percentage, 0), 100);

    card.innerHTML = `
      <!-- Cabecera -->
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2.5 truncate">
          <div class="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 font-bold flex items-center justify-center text-xs group-hover:bg-emerald-500/20 transition">
            ${m.programmer_name.substring(0, 2).toUpperCase()}
          </div>
          <div>
            <span class="text-sm font-semibold text-white truncate block group-hover:text-emerald-300 transition" title="${m.programmer_name}">
              ${m.programmer_name}
            </span>
            <span class="text-[10px] text-slate-500 block">Toca para ver historial</span>
          </div>
        </div>
        <span class="text-[10px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
          Activo
        </span>
      </div>

      <!-- Círculo de Ingresos -->
      <div class="flex items-center justify-center my-5">
        <div class="relative w-32 h-32">
          <svg class="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
            <path class="text-slate-800" stroke-width="3.2" stroke="currentColor" fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
            <path class="text-emerald-500 transition-all duration-700" stroke-width="3.2"
                  stroke-dasharray="${strokeVal}, 100" stroke-linecap="round" stroke="currentColor" fill="none"
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
          </svg>
          <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span class="text-xl font-black text-white font-mono tracking-tight">${revenuePct}%</span>
            <span class="text-[9px] text-emerald-400 font-semibold uppercase tracking-wider">de Ingresos</span>
          </div>
        </div>
      </div>

      <!-- Métricas Clave -->
      <div class="space-y-2.5 pt-3 border-t border-slate-800/80 text-xs">
        <div class="flex items-center justify-between text-slate-400">
          <span>Tareas Realizadas:</span>
          <span class="text-white font-bold font-mono">${m.total_accumulated}</span>
        </div>
        <div>
          <div class="flex items-center justify-between text-[11px] mb-1">
            <span class="text-slate-400">Eficacia en Tareas:</span>
            <span class="text-emerald-400 font-bold font-mono">${m.completion_rate.toFixed(0)}%</span>
          </div>
          <div class="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
            <div class="bg-emerald-500 h-1.5 rounded-full" style="width: ${Math.min(m.completion_rate, 100)}%"></div>
          </div>
        </div>
      </div>
    `;

    container.appendChild(card);
  });
}

function filterIndividualCards(query) {
  currentSearchQuery = query.trim();
  if (currentMetrics) renderRendimientoView(currentMetrics);
}

function sortIndividualCards(sortKey) {
  currentSortKey = sortKey;
  if (currentMetrics) renderRendimientoView(currentMetrics);
}

// -----------------------------------------------------------------------------
// MODAL: HISTORIAL Y ESPECIALIZACIÓN DEL INTEGRANTE (NUEVO)
// -----------------------------------------------------------------------------
async function openDevHistoryModal(name) {
  const modal = document.getElementById("modal-dev-history");
  document.getElementById("history-dev-name").textContent = name;
  document.getElementById("history-avatar").textContent = name.substring(0, 2).toUpperCase();
  const container = document.getElementById("history-sprints-container");
  container.innerHTML = `<p class="text-xs text-slate-400 py-6 text-center">Cargando historial de tareas...</p>`;
  openModal("modal-dev-history");

  try {
    const res = await authFetch(`/api/programmers/${encodeURIComponent(name)}/history`);
    if (!res.ok) throw new Error("No se pudo cargar el historial del integrante");
    const data = await res.json();

    document.getElementById("history-completed-tasks").textContent = data.total_completed;
    document.getElementById("history-revenue-pct").textContent = `${data.revenue_percentage?.toFixed(2) || 0}%`;
    document.getElementById("history-efficiency-pct").textContent = `${data.completion_rate?.toFixed(0) || 100}%`;

    if (!data.sprints || data.sprints.length === 0) {
      container.innerHTML = `
        <div class="p-6 bg-slate-950/60 rounded-xl border border-slate-800 text-center text-xs text-slate-500">
          Este integrante aún no tiene tareas asignadas en ningún sprint.
        </div>
      `;
      return;
    }

    let historyHtml = "";
    data.sprints.forEach(s => {
      let tasksListHtml = "";
      s.tasks.forEach(t => {
        const coWorkersBadge = t.co_workers && t.co_workers.length > 0
          ? `<span class="text-[11px] text-slate-400">En equipo con: <strong class="text-slate-200">${t.co_workers.join(", ")}</strong></span>`
          : `<span class="text-[11px] text-slate-500 italic">Trabajo individual</span>`;

        tasksListHtml += `
          <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800/80 flex items-center justify-between gap-3">
            <div class="flex items-center gap-2 truncate">
              <span class="w-1.5 h-1.5 rounded-full ${t.completed ? 'bg-emerald-400' : 'bg-amber-400'}"></span>
              <span class="text-xs font-medium text-slate-200 truncate">${t.title}</span>
            </div>
            <div class="flex items-center gap-3">
              ${coWorkersBadge}
              <span class="text-[10px] px-1.5 py-0.5 rounded font-medium ${t.completed ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}">
                ${t.completed ? 'Completada' : 'En progreso'}
              </span>
            </div>
          </div>
        `;
      });

      historyHtml += `
        <div class="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2.5">
          <div class="flex items-center justify-between border-b border-slate-800/80 pb-2">
            <div class="flex items-center gap-2">
              <span class="px-2 py-0.5 bg-slate-800 text-emerald-400 text-xs font-bold rounded border border-slate-700">
                Sprint ${s.sprint_number}
              </span>
              <span class="text-xs font-semibold text-white">${s.sprint_name}</span>
            </div>
            <span class="text-[11px] text-slate-400">${s.tasks.length} tarea(s) realizada(s)</span>
          </div>
          <div class="space-y-1.5">
            ${tasksListHtml}
          </div>
        </div>
      `;
    });

    container.innerHTML = historyHtml;
  } catch (err) {
    container.innerHTML = `<p class="text-xs text-rose-400 py-4">${err.message}</p>`;
  }
}

function updateFilterOptions(sprints) {
  const select = document.getElementById("filter-up-to");
  if (!select) return;
  const currentVal = select.value;
  select.innerHTML = '<option value="">Todos los sprints</option>';

  (sprints || []).forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s;
    opt.textContent = `Hasta Sprint ${s}`;
    if (String(s) === currentVal) opt.selected = true;
    select.appendChild(opt);
  });
}

// -----------------------------------------------------------------------------
// OPERACIONES DE SPRINT (Crear, Editar, Eliminar)
// -----------------------------------------------------------------------------
function openModalCreateSprint() {
  editingSprintNumber = null;
  document.getElementById("modal-sprint-title").textContent = "Agregar Nuevo Sprint";
  const nextNum = currentSprints.length > 0 ? Math.max(...currentSprints.map(s => s.sprint_number)) + 1 : 1;
  document.getElementById("input-sprint-number").value = nextNum;
  document.getElementById("input-sprint-number").disabled = false;
  document.getElementById("input-sprint-name").value = `Sprint ${nextNum}`;
  document.getElementById("input-sprint-status").value = "completed";

  const container = document.getElementById("tasks-container");
  container.innerHTML = "";
  addTaskRow("Tarea 1", "completed");

  openModal("modal-sprint");
}

function addTaskRow(initialTitle = "", initialStatus = "completed", selectedDevs = []) {
  const container = document.getElementById("tasks-container");
  const taskIndex = container.children.length + 1;
  const row = document.createElement("div");
  row.className = "task-row bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-2.5 relative";

  const activeProgs = currentProgrammers.filter(p => p.active);
  let devCheckboxes = "";
  if (activeProgs.length === 0) {
    devCheckboxes = `<span class="text-[11px] text-amber-400">No hay integrantes activos. Primero agrégalos en el menú Acciones.</span>`;
  } else {
    devCheckboxes = activeProgs.map(p => {
      const isChecked = selectedDevs.includes(p.name);
      return `
        <label class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-700/80 text-xs text-slate-200 cursor-pointer hover:bg-slate-800 transition">
          <input type="checkbox" value="${p.name}" class="task-dev-checkbox rounded border-slate-700 text-emerald-500 focus:ring-emerald-500" ${isChecked ? 'checked' : ''}>
          <span>${p.name}</span>
        </label>
      `;
    }).join(" ");
  }

  row.innerHTML = `
    <div class="flex items-center justify-between gap-3">
      <div class="flex-1">
        <input type="text" value="${initialTitle || `Tarea ${taskIndex}`}" class="task-title-input w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:ring-1 focus:ring-emerald-500" placeholder="Nombre de la tarea">
      </div>
      <div class="w-32">
        <select class="task-status-select w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:ring-1 focus:ring-emerald-500">
          <option value="completed" ${initialStatus === 'completed' ? 'selected' : ''}>Completada</option>
          <option value="in_progress" ${initialStatus === 'in_progress' ? 'selected' : ''}>En progreso</option>
        </select>
      </div>
      <button type="button" onclick="this.closest('.task-row').remove()" class="text-slate-500 hover:text-rose-400 text-xs px-2 py-1 transition" title="Eliminar tarea">
        ✕
      </button>
    </div>

    <div>
      <span class="block text-[11px] font-medium text-slate-400 mb-1.5">Integrantes Asignados (colaboradores en esta tarea):</span>
      <div class="flex flex-wrap gap-2">
        ${devCheckboxes}
      </div>
    </div>
  `;

  container.appendChild(row);
}

async function saveSprintSubmit() {
  const sprintNum = parseInt(document.getElementById("input-sprint-number").value, 10);
  const name = document.getElementById("input-sprint-name").value.trim();
  const status = document.getElementById("input-sprint-status").value;

  if (!sprintNum || sprintNum <= 0) {
    showToast("Ingresa un número de sprint válido", "error");
    return;
  }
  if (!name) {
    showToast("Ingresa un nombre para el sprint", "error");
    return;
  }

  const rows = document.querySelectorAll(".task-row");
  const tasks = [];

  rows.forEach((row) => {
    const title = row.querySelector(".task-title-input").value.trim();
    const tStatus = row.querySelector(".task-status-select").value;
    const checkboxes = row.querySelectorAll(".task-dev-checkbox:checked");
    const assignedDevs = Array.from(checkboxes).map(c => c.value);

    if (title) {
      tasks.push({
        title: title,
        status: tStatus,
        assigned_programmers: assignedDevs
      });
    }
  });

  const payload = {
    sprint_number: sprintNum,
    name: name,
    status: status,
    tasks: tasks
  };

  try {
    const method = editingSprintNumber !== null ? "PUT" : "POST";
    const url = editingSprintNumber !== null ? `/api/sprints/${editingSprintNumber}` : "/api/sprints";

    const res = await authFetch(url, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Error al guardar sprint");
    }

    closeModal("modal-sprint");
    showToast(`Sprint ${sprintNum} guardado con éxito`);
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}





function openModalEditSprintSelect() {
  const select = document.getElementById("select-edit-sprint-id");
  select.innerHTML = "";

  if (currentSprints.length === 0) {
    showToast("No hay sprints registrados para editar", "error");
    return;
  }

  currentSprints.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.sprint_number;
    opt.textContent = `Sprint ${s.sprint_number} - ${s.name}`;
    select.appendChild(opt);
  });

  openModal("modal-select-edit-sprint");
}

async function proceedToEditSprint() {
  const sprintNum = parseInt(document.getElementById("select-edit-sprint-id").value, 10);
  closeModal("modal-select-edit-sprint");

  try {
    const res = await authFetch(`/api/sprints/${sprintNum}`);
    if (!res.ok) throw new Error("Error al obtener datos del sprint");
    const data = await res.json();

    editingSprintNumber = data.sprint_number;
    document.getElementById("modal-sprint-title").textContent = `Editar Sprint ${data.sprint_number}`;
    document.getElementById("input-sprint-number").value = data.sprint_number;
    document.getElementById("input-sprint-number").disabled = true;
    document.getElementById("input-sprint-name").value = data.name;
    document.getElementById("input-sprint-status").value = data.status;

    const container = document.getElementById("tasks-container");
    container.innerHTML = "";

    if (data.tasks && data.tasks.length > 0) {
      data.tasks.forEach(t => {
        addTaskRow(t.title, t.status, t.assigned_programmers);
      });
    } else {
      addTaskRow("Tarea 1", "completed");
    }

    openModal("modal-sprint");
  } catch (err) {
    showToast(err.message, "error");
  }
}





function openModalDeleteSprintSelect() {
  const select = document.getElementById("select-delete-sprint-id");
  select.innerHTML = "";

  if (currentSprints.length === 0) {
    showToast("No hay sprints registrados para eliminar", "error");
    return;
  }

  currentSprints.forEach(s => {
    const opt = document.createElement("option");
    opt.value = s.sprint_number;
    opt.textContent = `Sprint ${s.sprint_number} - ${s.name}`;
    select.appendChild(opt);
  });

  openModal("modal-delete-sprint");
}

async function confirmDeleteSprint() {
  const sprintNum = parseInt(document.getElementById("select-delete-sprint-id").value, 10);
  if (!sprintNum) return;

  try {
    const res = await authFetch(`/api/sprints/${sprintNum}`, { method: "DELETE" });
    if (!res.ok) throw new Error("Error al eliminar sprint");
    closeModal("modal-delete-sprint");
    showToast(`Sprint ${sprintNum} eliminado correctamente`);
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}





// -----------------------------------------------------------------------------
// OPERACIONES DE INTEGRANTES (Agregar, Editar, Eliminar)
// -----------------------------------------------------------------------------
function openModalAddDev() {
  document.getElementById("input-new-dev-name").value = "";
  openModal("modal-add-dev");
}

async function submitAddDev() {
  const name = document.getElementById("input-new-dev-name").value.trim();
  if (!name) {
    showToast("Ingresa un nombre para el integrante", "error");
    return;
  }

  try {
    const res = await authFetch("/api/programmers", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name })
    });
    if (!res.ok) throw new Error("Error al registrar integrante");
    closeModal("modal-add-dev");
    showToast(`Integrante '${name}' agregado`);
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}





function openModalEditDevSelect() {
  const select = document.getElementById("select-edit-dev-old");
  select.innerHTML = "";

  if (currentProgrammers.length === 0) {
    showToast("No hay integrantes para editar", "error");
    return;
  }

  currentProgrammers.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    select.appendChild(opt);
  });

  onDevSelectChange();
  openModal("modal-edit-dev");
}

function onDevSelectChange() {
  const select = document.getElementById("select-edit-dev-old");
  const input = document.getElementById("input-edit-dev-new-name");
  input.value = select.value;
}

async function submitEditDev() {
  const oldName = document.getElementById("select-edit-dev-old").value;
  const newName = document.getElementById("input-edit-dev-new-name").value.trim();

  if (!newName) {
    showToast("Ingresa un nombre válido", "error");
    return;
  }

  try {
    const res = await authFetch("/api/programmers", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        old_name: oldName,
        new_name: newName,
        active: true
      })
    });
    if (!res.ok) throw new Error("Error al actualizar integrante");
    closeModal("modal-edit-dev");
    showToast(`Integrante actualizado a '${newName}'`);
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}





function openModalDeleteDevSelect() {
  const select = document.getElementById("select-delete-dev-name");
  select.innerHTML = "";

  if (currentProgrammers.length === 0) {
    showToast("No hay integrantes para eliminar", "error");
    return;
  }

  currentProgrammers.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    select.appendChild(opt);
  });

  openModal("modal-delete-dev");
}

async function confirmDeleteDev() {
  const name = document.getElementById("select-delete-dev-name").value;
  if (!name) return;

  try {
    const res = await authFetch(`/api/programmers/${encodeURIComponent(name)}`, {
      method: "DELETE"
    });
    if (!res.ok) throw new Error("Error al eliminar integrante");
    closeModal("modal-delete-dev");
    showToast(`Integrante '${name}' eliminado`);
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}





// -----------------------------------------------------------------------------
// Exportación
// -----------------------------------------------------------------------------
async function exportData(format) {
  const upToVal = document.getElementById("filter-up-to")?.value;
  let url = `/api/export?format=${format}`;
  if (upToVal) url += `&up_to=${upToVal}`;

  try {
    const res = await authFetch(url);
    if (!res.ok) throw new Error("Error al exportar datos");
    const blob = await res.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `taskmetrics_rendimiento.${format === 'md' ? 'md' : 'csv'}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    showToast(`Reporte .${format} descargado correctamente`);
  } catch (err) {
    showToast(err.message, "error");
  }
}

// =============================================================================
// GESTIÓN DE USUARIOS Y ROLES (Exclusivo Administrador)
// =============================================================================

let currentAdminUsers = [];

async function loadUsersList() {
  const tbody = document.getElementById("users-table-body");
  if (!tbody) return;

  try {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-8 text-center text-slate-500">
          <div class="flex items-center justify-center gap-2">
            <span class="animate-spin">⏳</span>
            <span>Cargando usuarios...</span>
          </div>
        </td>
      </tr>
    `;

    const res = await authFetch("/api/admin/users");
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "No se pudieron obtener los usuarios.");
    }

    const data = await res.json();
    currentAdminUsers = data.users || [];
    renderUsersTable();
  } catch (err) {
    if (tbody) {
      tbody.innerHTML = `
        <tr>
          <td colspan="5" class="py-6 text-center text-rose-400">
            Error al cargar usuarios: ${escapeHtml(err.message)}
          </td>
        </tr>
      `;
    }
    showToast(err.message, "error");
  }
}

function renderUsersTable() {
  const tbody = document.getElementById("users-table-body");
  if (!tbody) return;

  if (currentAdminUsers.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="5" class="py-8 text-center text-slate-500">
          No hay usuarios registrados en el sistema.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = currentAdminUsers.map(u => {
    const isMe = currentUser && currentUser.id === u.id;
    const roleBadge = u.role === "admin"
      ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">👑 Administrador</span>'
      : '<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">⭐ Líder</span>';

    const statusBadge = u.active
      ? '<span class="text-emerald-400 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Activo</span>'
      : '<span class="text-rose-400 flex items-center gap-1.5"><span class="w-1.5 h-1.5 rounded-full bg-rose-400"></span> Inactivo</span>';

    const escapedName = escapeHtml(u.name || "Sin nombre");
    const escapedEmail = escapeHtml(u.email);
    const userSafeId = escapeHtml(u.id);

    return `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-3.5 px-4 font-medium text-white flex items-center gap-2">
          <div class="w-7 h-7 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-slate-300 text-xs">
            ${escapedName.charAt(0).toUpperCase()}
          </div>
          <div>
            <div>${escapedName}</div>
            ${isMe ? '<span class="text-[10px] text-emerald-400 font-semibold">(Tú)</span>' : ''}
          </div>
        </td>
        <td class="py-3.5 px-4 text-slate-300">${escapedEmail}</td>
        <td class="py-3.5 px-4">${roleBadge}</td>
        <td class="py-3.5 px-4">${statusBadge}</td>
        <td class="py-3.5 px-4 text-right">
          <div class="inline-flex items-center gap-1.5">
            <button onclick="onEditUserClick('${userSafeId}')"
                    class="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-medium border border-slate-700 transition flex items-center gap-1"
                    title="Editar usuario y permisos">
              <span>✏️</span>
              <span class="hidden sm:inline">Editar</span>
            </button>
            <button onclick="deleteUserAdmin('${userSafeId}', '${escapedName}')"
                    ${isMe ? 'disabled title="No puedes eliminar tu propia cuenta" class="px-2.5 py-1.5 bg-slate-900 text-slate-600 rounded-lg text-xs border border-slate-800 cursor-not-allowed"' : 'class="px-2.5 py-1.5 bg-rose-950/40 hover:bg-rose-900/60 text-rose-300 rounded-lg text-xs font-medium border border-rose-800/60 transition" title="Eliminar usuario"'} >
              <span>🗑️</span>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function onEditUserClick(userId) {
  const user = currentAdminUsers.find(u => u.id === userId);
  if (user) {
    openModalEditUser(user);
  }
}

function openModalCreateUser() {
  document.getElementById("form-admin-create-user")?.reset();
  const errBox = document.getElementById("admin-create-user-error");
  if (errBox) {
    errBox.classList.add("hidden");
    errBox.textContent = "";
  }
  openModal("modal-admin-create-user");
}

async function submitAdminCreateUser() {
  const name = document.getElementById("admin-user-name")?.value.trim();
  const email = document.getElementById("admin-user-email")?.value.trim();
  const password = document.getElementById("admin-user-password")?.value;
  const role = document.getElementById("admin-user-role")?.value || "lider";
  const errBox = document.getElementById("admin-create-user-error");
  const submitBtn = document.getElementById("btn-submit-create-user");

  if (!name || !email || !password) {
    if (errBox) {
      errBox.textContent = "Por favor completa todos los campos requeridos.";
      errBox.classList.remove("hidden");
    }
    return;
  }

  try {
    if (submitBtn) submitBtn.disabled = true;
    if (errBox) errBox.classList.add("hidden");

    const res = await authFetch("/api/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name, role })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "No se pudo crear el usuario.");
    }

    closeModal("modal-admin-create-user");
    showToast(`¡Usuario ${data.name || data.email} creado con éxito con rol de ${data.role === 'admin' ? 'Administrador' : 'Líder'}!`);
    loadUsersList();
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message || "Error al crear usuario.";
      errBox.classList.remove("hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

function openModalEditUser(user) {
  if (!user) return;
  const errBox = document.getElementById("admin-edit-user-error");
  if (errBox) {
    errBox.classList.add("hidden");
    errBox.textContent = "";
  }

  document.getElementById("edit-user-id").value = user.id;
  document.getElementById("edit-user-name").value = user.name || "";
  document.getElementById("edit-user-email").value = user.email || "";
  document.getElementById("edit-user-role").value = user.role || "lider";
  document.getElementById("edit-user-active").value = user.active ? "true" : "false";
  document.getElementById("edit-user-password").value = "";

  openModal("modal-admin-edit-user");
}

async function submitAdminEditUser() {
  const userId = document.getElementById("edit-user-id")?.value;
  const name = document.getElementById("edit-user-name")?.value.trim();
  const role = document.getElementById("edit-user-role")?.value;
  const active = document.getElementById("edit-user-active")?.value === "true";
  const password = document.getElementById("edit-user-password")?.value;
  const errBox = document.getElementById("admin-edit-user-error");
  const submitBtn = document.getElementById("btn-submit-edit-user");

  if (!userId || !name) {
    if (errBox) {
      errBox.textContent = "El nombre es obligatorio.";
      errBox.classList.remove("hidden");
    }
    return;
  }

  const payload = { name, role, active };
  if (password && password.trim().length >= 6) {
    payload.password = password.trim();
  }

  try {
    if (submitBtn) submitBtn.disabled = true;
    if (errBox) errBox.classList.add("hidden");

    const res = await authFetch(`/api/admin/users/${userId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "No se pudo actualizar el usuario.");
    }

    closeModal("modal-admin-edit-user");
    showToast("Usuario actualizado correctamente.");

    // Si el usuario editado es el actual, refrescar sesión local
    if (currentUser && currentUser.id === userId) {
      currentUser.name = data.name;
      currentUser.role = data.role;
      updateAuthUI();
    }

    loadUsersList();
  } catch (err) {
    if (errBox) {
      errBox.textContent = err.message || "Error al actualizar el usuario.";
      errBox.classList.remove("hidden");
    }
  } finally {
    if (submitBtn) submitBtn.disabled = false;
  }
}

async function deleteUserAdmin(userId, userName) {
  if (!confirm(`¿Estás seguro de eliminar permanentemente al usuario "${userName}"? Esta acción no se puede deshacer.`)) {
    return;
  }

  try {
    const res = await authFetch(`/api/admin/users/${userId}`, {
      method: "DELETE"
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "No se pudo eliminar el usuario.");
    }
    showToast(`Usuario "${userName}" eliminado.`);
    loadUsersList();
  } catch (err) {
    showToast(err.message, "error");
  }
}

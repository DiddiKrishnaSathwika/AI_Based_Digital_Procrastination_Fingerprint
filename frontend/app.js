/* ProcrastiSense AI — frontend application logic (vanilla JS SPA) */

const API = ""; // same-origin, Flask serves both API + static frontend

const PAGES = [
  { id: "dashboard",     label: "Dashboard",         icon: "grid" },
  { id: "fingerprint",   label: "My Fingerprint",    icon: "fingerprint" },
  { id: "timeline",      label: "Activity Timeline", icon: "clock" },
  { id: "analytics",     label: "Analytics",         icon: "chart" },
  { id: "prediction",    label: "Prediction",        icon: "target" },
  { id: "interventions", label: "Interventions",     icon: "shield" },
  { id: "collection",    label: "Data Collection",   icon: "plus" },
  { id: "privacy",       label: "Privacy",           icon: "lock" },
];

const ICONS = {
  grid: '<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z" stroke="currentColor" stroke-width="1.6" fill="none"/>',
  fingerprint: '<path d="M12 2a8 8 0 0 0-8 8c0 5 3 7 3 12M12 2a8 8 0 0 1 8 8c0 3-1 5-1 8M12 6a4 4 0 0 0-4 4c0 6 4 8 4 12M12 6a4 4 0 0 1 4 4c0 2-.5 3.5-.5 5" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>',
  clock: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6" fill="none"/><path d="M12 7v5l3 3" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round"/>',
  chart: '<path d="M4 20V10M12 20V4M20 20v-7" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  target: '<circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.5" fill="none"/><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="1.5" fill="none"/><circle cx="12" cy="12" r="1" fill="currentColor"/>',
  shield: '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3z" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linejoin="round"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  flow: '<circle cx="5" cy="6" r="2.2" stroke="currentColor" stroke-width="1.4" fill="none"/><circle cx="19" cy="12" r="2.2" stroke="currentColor" stroke-width="1.4" fill="none"/><circle cx="5" cy="18" r="2.2" stroke="currentColor" stroke-width="1.4" fill="none"/><path d="M7 6h6a4 4 0 0 1 4 4v0M7 18h6a4 4 0 0 0 4-4v0" stroke="currentColor" stroke-width="1.3" fill="none"/>',
  lock: '<rect x="5" y="11" width="14" height="9" rx="2" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M8 11V8a4 4 0 0 1 8 0v3" stroke="currentColor" stroke-width="1.5" fill="none"/>',
  info: '<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5" fill="none"/><path d="M12 11v5M12 8v.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
};

let charts = {};
let currentPage = "dashboard";

/* ---------------- Navigation / shell ---------------- */
function buildSideNav() {
  const nav = document.getElementById("side-nav");
  nav.innerHTML = PAGES.map(p => `
    <a href="#" class="side-link ${p.id === currentPage ? "active" : ""}" data-page="${p.id}" onclick="goPage('${p.id}');return false;">
      <svg viewBox="0 0 24 24">${ICONS[p.icon]}</svg>${p.label}
    </a>`).join("");
}

function goPage(id) {
  currentPage = id;
  document.querySelectorAll(".page").forEach(el => el.classList.remove("active"));
  document.getElementById("page-" + id).classList.add("active");
  document.querySelectorAll(".side-link").forEach(el => el.classList.toggle("active", el.dataset.page === id));
  document.getElementById("sidebar").classList.remove("open");
  loadPageData(id);
}


function enterApp() {
  document.getElementById("landing").style.display = "none";
  document.getElementById("app").style.display = "none";

  const auth = document.getElementById("auth-screen");
  auth.style.display = "flex";

  showAuthForm("login");
}

function exitApp() {
  document.getElementById("app").style.display = "none";
  document.getElementById("landing").style.display = "block";
  window.scrollTo(0, 0);
}

function toggleDemo() {
  const switchEl = document.getElementById("demo-switch");

  switchEl.classList.toggle("on");

  document.body.classList.toggle("light-mode", !switchEl.classList.contains("on"));
}

function showAuthForm(form) {
  const forms = ["login", "register"];

  forms.forEach(name => {
    document.getElementById(name + "-form").style.display =
      name === form ? "block" : "none";
  });
}

function backToLanding() {
  document.getElementById("auth-screen").style.display = "none";
  document.getElementById("landing").style.display = "block";
  window.scrollTo(0, 0);
}




async function loginUser(event) {
  event.preventDefault();

  const email = document.getElementById("login-email").value.trim();
  const password = document.getElementById("login-password").value;

  try {
    const response = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email, password })
    });

    const data = await response.json();

    if (!response.ok) {
      showToast(data.message || "Login failed.");
      return false;
    }

    // Fetch the logged-in user's details
    const userResponse = await fetch(`${API}/api/auth/me`, {
      credentials: "same-origin"
    });

    if (!userResponse.ok) {
      showToast("Unable to load your account details.");
      return false;
    }

    const userData = await userResponse.json();

    document.getElementById("dashboard-user-name").textContent =
      userData.user.name || "User";

    showToast("Login successful!");
    openDashboard();

  } catch (error) {
    showToast("Unable to connect to the server.");
  }

  return false;
}


async function registerUser(event) {
  event.preventDefault();

  const full_name = document.getElementById("register-name").value.trim();
  const email = document.getElementById("register-email").value.trim();
  const password = document.getElementById("register-password").value;

  try {
    const response = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        full_name,
        email,
        password
      })
    });

    const data = await response.json();

    if (!response.ok) {
      showToast(data.message || "Account creation failed.");
      return false;
    }

    document.getElementById("login-email").value = email;
    document.getElementById("login-password").value = "";
    showAuthForm("login");
    showToast(data.message || "Account created. You can now log in.");

  } catch (error) {
    showToast("Unable to connect to the server.");
  }

  return false;
}


async function logoutUser() {
  try {
    const response = await fetch(`${API}/api/auth/logout`, {
      method: "POST",
      credentials: "same-origin"
    });

    if (!response.ok) {
      showToast("Unable to log out. Please try again.");
      return;
    }

    document.getElementById("app").style.display = "none";
    document.getElementById("auth-screen").style.display = "none";
    document.getElementById("landing").style.display = "block";

    window.scrollTo(0, 0);
    showToast("Logged out successfully.");

  } catch (error) {
    showToast("Unable to log out. Please try again.");
  }
}

async function deleteAccount(event) {
  event.preventDefault();

  if (!window.confirm("Delete your account and all associated activity data? This cannot be undone.")) {
    return false;
  }

  const password = document.getElementById("delete-account-password").value;

  try {
    const response = await fetch(`${API}/api/auth/delete-account`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ password })
    });

    const data = await response.json();

    if (!response.ok) {
      showToast(data.message || "Account deletion failed.");
      return false;
    }

    document.getElementById("delete-account-form").reset();
    document.getElementById("app").style.display = "none";
    document.getElementById("auth-screen").style.display = "none";
    document.getElementById("landing").style.display = "block";
    window.scrollTo(0, 0);
    showToast(data.message || "Your account has been deleted.");
  } catch (error) {
    showToast("Unable to connect to the server.");
  }

  return false;
}

function generatePassword() {
  const groups = [
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "!@#$%^&*_-"
  ];

  const allCharacters = groups.join("");
  const passwordCharacters = groups.map(group => {
    const random = new Uint32Array(1);
    crypto.getRandomValues(random);
    return group[random[0] % group.length];
  });

  const random = new Uint32Array(1);

  for (let i = passwordCharacters.length - 1; i > 0; i--) {
    crypto.getRandomValues(random);
    const j = random[0] % (i + 1);

    [passwordCharacters[i], passwordCharacters[j]] =
      [passwordCharacters[j], passwordCharacters[i]];
  }

  while (passwordCharacters.length < 16) {
    crypto.getRandomValues(random);
    passwordCharacters.push(
      allCharacters[random[0] % allCharacters.length]
    );
  }

  for (let i = passwordCharacters.length - 1; i > 0; i--) {
    crypto.getRandomValues(random);
    const j = random[0] % (i + 1);

    [passwordCharacters[i], passwordCharacters[j]] =
      [passwordCharacters[j], passwordCharacters[i]];
  }

  const password = passwordCharacters.join("");

  document.getElementById("register-password").value = password;

  showToast("Strong password generated!");
}

function openDashboard() {
  document.getElementById("landing").style.display = "none";
  document.getElementById("auth-screen").style.display = "none";
  document.getElementById("app").style.display = "block";

  buildSideNav();
  goPage("dashboard");
}

function showToast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 3200);
}

/* ---------------- Data loading router ---------------- */
function loadPageData(id) {
  if (id === "dashboard") loadDashboard();
  if (id === "fingerprint") loadFingerprint();
  if (id === "timeline") loadTimeline("All");
  if (id === "analytics") loadAnalytics();
  if (id === "prediction") loadPrediction();
  if (id === "interventions") loadInterventions();
  if (id === "collection") loadRecords();
}

/* ---------------- Dashboard ---------------- */
async function loadDashboard() {
  const r = await fetch(`${API}/api/dashboard`).then(x => x.json());
  const cards = [
    { label: "Focus Score", value: r.focus_score + "%", cls: "focus-c", sub: "of tracked time" },
    {
  label: "Distraction Probability",
  value: r.distraction_probability === null
    ? "No data"
    : r.distraction_probability + "%",
  cls: "distract-c",
  sub: r.distraction_probability === null
    ? "Start tracking your activity"
    : "prototype prediction"
},
    { label: "Today's Focus Time", value: fmtMin(r.today_focus_time_min), cls: "", sub: "focused sessions" },
    { label: "Distractions", value: r.distractions, cls: "", sub: "events recorded" },
    { label: "Application Switches", value: r.app_switches, cls: "", sub: "context switches" },
    { label: "Avg Focus Session", value: r.avg_focus_session_min + " min", cls: "", sub: "per session" },
  ];
  document.getElementById("dash-metrics").innerHTML = cards.map(c => `
    <div class="card metric-card">
      <div class="label">${c.label}</div>
      <div class="value ${c.cls}">${c.value}</div>
      <div class="sub">${c.sub}</div>
    </div>`).join("");
}

function fmtMin(m) {
  const h = Math.floor(m / 60), mm = Math.round(m % 60);
  return h > 0 ? `${h}h ${mm}m` : `${mm}m`;
}

/* ---- Live session timer ---- */
let sessionInterval = null, sessionSeconds = 0;
const CIRC = 2 * Math.PI * 64;



async function startSession() {

    const taskType = document.getElementById("task-select").value;
    const difficulty = document.getElementById("difficulty-select").value;

    try {

        // Step 1: Save the active task in Flask
        const taskResponse = await fetch(`${API}/api/task/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                task_type: taskType,
                task_difficulty: difficulty
            })
        });

        const taskData = await taskResponse.json();

        if (!taskResponse.ok) {
            showToast(taskData.message || "Unable to start tracking.");
            return;
        }

        // Step 2: Generate the collector authentication token
        const tokenResponse = await fetch(`${API}/api/collector/token`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });

        const tokenData = await tokenResponse.json();

        if (!tokenResponse.ok || !tokenData.token) {
            await fetch(`${API}/api/task/stop`, { method: "POST" });
            showToast("Unable to authenticate the desktop collector.");
            return;
        }

        // Step 3: Send task and token to the local collector bridge
        const bridgeResponse = await fetch("http://127.0.0.1:5051/task", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                action: "start",
                token: tokenData.token,
                task_type: taskType,
                task_difficulty: difficulty
            })
        });

        if (!bridgeResponse.ok) {
            await fetch(`${API}/api/task/stop`, { method: "POST" });
            showToast("Desktop collector is not running.");
            return;
        }

        // Update dashboard interface
        sessionSeconds = 0;

        document.getElementById("start-session-btn").disabled = true;
        document.getElementById("end-session-btn").disabled = false;

        document.getElementById("cur-app").textContent = taskType;
        document.getElementById("session-app-text").textContent = taskType;

        document.getElementById("warning-content").innerHTML =
            `<p class="empty">Session running — monitoring your activity...</p>`;

        clearInterval(sessionInterval);
        sessionInterval = setInterval(tickSession, 1000);
        tickSession();

        showToast("Task tracking started successfully.");

    } catch (error) {

        console.error("Start tracking error:", error);
        showToast("Unable to connect. Check that the desktop collector is running.");

    }
}



function tickSession() {
  sessionSeconds++;
  const mm = String(Math.floor(sessionSeconds / 60)).padStart(2, "0");
  const ss = String(sessionSeconds % 60).padStart(2, "0");
  document.getElementById("session-timer-text").textContent = `${mm}:${ss}`;

  // progress ring maxes visually at 30 min
  const pct = Math.min(1, sessionSeconds / (30 * 60));
  document.getElementById("session-progress").style.strokeDashoffset = CIRC * (1 - pct);

  const mins = sessionSeconds / 60;
  let risk = "Low", badgeClass = "risk-low";
  if (mins >= 23 && mins < 28) { risk = "Moderate"; badgeClass = "risk-moderate"; }
  else if (mins >= 28) { risk = "High"; badgeClass = "risk-high"; }
  document.getElementById("cur-risk").textContent = risk;
  document.getElementById("session-risk-badge").textContent = risk;
  document.getElementById("session-risk-badge").className = "badge " + badgeClass;

  if (mins >= 23 && mins < 23.05) {
    document.getElementById("warning-content").innerHTML = `
      <div class="alert-box">
        <div class="icon">⚠️</div>
        <div>
          <h4>Distraction risk increasing</h4>
          <p>Your current session is approaching your usual distraction window (23–28 minutes).</p>
          <div class="rec"><b>Recommended:</b> take a 5-minute break before starting another focused session.</div>
          <div class="btn-row">
            <button class="btn btn-primary btn-sm" onclick="breakNow()">Start 5-Minute Break</button>
            <button class="btn btn-sm" onclick="continueWorking()">Continue Working</button>
          </div>
        </div>
      </div>`;
  }
}

function breakNow() {
  document.getElementById("warning-content").innerHTML = `<p class="empty">Break noted. The session timer keeps running and the collector keeps recording until you end the session.</p>`;
  showToast("Break started — nice, proactive move.");
}
function continueWorking() {
  document.getElementById("warning-content").innerHTML = `<p class="empty">Continuing session — we'll keep watching for the next risk signal.</p>`;
}



async function endSession() {

    clearInterval(sessionInterval);

    try {

        // Stop the task in Flask
        const response = await fetch(`${API}/api/task/stop`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });

        if (!response.ok) {
            showToast("Unable to stop tracking in the backend.");
            return;
        }

        // Stop the desktop collector
        const bridgeResponse = await fetch("http://127.0.0.1:5051/task", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                action: "stop"
            })
        });

        if (!bridgeResponse.ok) {
            showToast("Backend stopped, but collector connection failed.");
        } else {
            showToast("Task tracking stopped successfully.");
        }

    } catch (error) {

        console.error("Stop tracking error:", error);
        showToast("Unable to connect to the tracking service.");

    }

    // Reset dashboard interface
    document.getElementById("start-session-btn").disabled = false;
    document.getElementById("end-session-btn").disabled = true;

    document.getElementById("session-app-text").textContent = "Not started";
    document.getElementById("session-timer-text").textContent = "00:00";
    document.getElementById("session-progress").style.strokeDashoffset = CIRC;

    document.getElementById("cur-app").textContent = "—";
    document.getElementById("cur-risk").textContent = "—";

    document.getElementById("session-risk-badge").textContent = "Idle";
    document.getElementById("session-risk-badge").className = "badge";

    document.getElementById("warning-content").innerHTML =
        `<p class="empty">Start a focus session to enable live distraction warnings.</p>`;

    sessionSeconds = 0;
}



/* ---------------- Weekly report modal ---------------- */
async function openReport() {
  const r = await fetch(`${API}/api/weekly-report`).then(x => x.json());
  const row = (k, v) => `<div><b style="color:var(--text)">${k}</b> ${v}</div>`;
  let change;
  if (r.comparison_available) {
    const c = r.focus_score_change_pp;
    change = `${c > 0 ? "+" : ""}${c} percentage points (focus score ${r.previous_focus_score}% \u2192 ${r.current_focus_score}%)`;
  } else {
    change = `<span style="color:var(--muted-2)">Not available &mdash; ${r.comparison_note}</span>`;
  }
  if (!r.has_data) {
    document.getElementById("report-body").innerHTML =
      row("Your last 7 days", "") + `<div>${r.comparison_note}</div>` +
      `<div style="font-size:11.5px;color:var(--muted-2);margin-top:6px;">${r.label}</div>`;
  } else {
    const days = (r.best_day && r.worst_day)
      ? row("Best Day:", r.best_day) + row("Worst Day:", r.worst_day)
      : row("Best / Worst Day:", `<span style="color:var(--muted-2)">Needs at least 2 days with enough tracked time</span>`);
    document.getElementById("report-body").innerHTML = `
      ${row("Total Focus Time:", fmtMin(r.total_focus_time_min))}
      ${row("Total Distraction Time:", fmtMin(r.total_distraction_time_min))}
      ${row("Avg Focus Session:", r.avg_focus_session_min + " min")}
      ${row("Distraction Events:", r.distraction_events)}
      ${row("Most Distracting Category:", r.most_distracting_category || "None recorded")}
      ${days}
      ${row("Change vs. previous week:", change)}
      <div style="font-size:11.5px;color:var(--muted-2);margin-top:6px;">${r.label}</div>`;
  }
  document.getElementById("report-modal").classList.add("open");
}
function closeReport() { document.getElementById("report-modal").classList.remove("open"); }

/* ---------------- Fingerprint ---------------- */
async function loadFingerprint() {
  try {
    const fingerprintResponse = await fetch(`${API}/api/fingerprint`);
    if (!fingerprintResponse.ok) {
      throw new Error(`Fingerprint API returned HTTP ${fingerprintResponse.status}`);
    }

    const fp = await fingerprintResponse.json();
    if (!fp || typeof fp !== "object" || Array.isArray(fp)) {
      throw new Error("Fingerprint API returned an invalid response.");
    }

    const activityResponse = await fetch(`${API}/api/activity?limit=60`);
    if (!activityResponse.ok) {
      throw new Error(`Activity API returned HTTP ${activityResponse.status}`);
    }

    const rows = await activityResponse.json();
    if (!Array.isArray(rows) || !rows.every(row =>
      row && typeof row === "object" && !Array.isArray(row)
    )) {
      throw new Error("Activity API returned an invalid response.");
    }

    const displayText = value =>
      typeof value === "string" && value.trim()
        ? value
        : "Insufficient data";
    const displayMinutes = value =>
      Number.isFinite(value) ? `${value} min` : "Insufficient data";
    const windowRange = Array.isArray(fp.typical_distraction_window)
      && fp.typical_distraction_window.length === 2
      && fp.typical_distraction_window.every(Number.isFinite)
      ? `${fp.typical_distraction_window.join("–")} min`
      : "Insufficient data";

    document.getElementById("fp-narrative").textContent =
      displayText(fp.narrative);
    const metrics = [
      ["Typical Focus Duration", displayMinutes(fp.typical_focus_duration_min)],
      ["Typical Distraction Window", windowRange],
      ["App Switching Pattern", displayText(fp.app_switching_pattern)],
      ["Most Frequent Distraction", displayText(fp.most_frequent_distraction)],
      ["Most Risky Task", displayText(fp.most_risky_task)],
      ["Most Risky Time", displayText(fp.most_risky_time)],
      ["Average Distraction Episode", displayMinutes(fp.average_recovery_time_min)],
      ["Source", displayText(fp.label)],
    ];
    const metricsContainer = document.getElementById("fp-metrics");
    metricsContainer.replaceChildren(...metrics.map(([label, value]) => {
      const tile = document.createElement("div");
      tile.className = "tile";

      const heading = document.createElement("div");
      heading.className = "num";
      heading.textContent = label.toUpperCase();

      const metricValue = document.createElement("h3");
      metricValue.style.fontSize = "15px";
      metricValue.style.marginTop = "8px";
      metricValue.textContent = value;

      tile.append(heading, metricValue);
      return tile;
    }));

    drawFingerprintRing("fingerprint-viz", rows, 300);
  } catch (error) {
    console.error("Fingerprint load error:", error);
    document.getElementById("fp-narrative").textContent =
      "Fingerprint data could not be loaded.";
    document.getElementById("fp-metrics").textContent = "";
    document.getElementById("fingerprint-viz").innerHTML = "";
    showToast("Unable to load fingerprint data. Please try again.");
  }
}







function drawFingerprintRing(svgId, rows, size) {
  const svg = document.getElementById(svgId);
  if (!svg) return;

  const cx = size / 2;
  const cy = size / 2;

  const colors = {
    Focused: "#4CD6C0",
    Distracted: "#FF6B6B",
    Idle: "#6C7A96"
  };

  const activityRows = Array.isArray(rows) ? rows : [];
  const escapeSvgText = value => String(value).replace(/[&<>]/g, character => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;"
  })[character]);

  let html = "";

  const ringCount = 5;

  // Empty activity state
  if (activityRows.length === 0) {
    for (let ring = 0; ring < ringCount; ring++) {
      const r = 40 + ring * (size / 2 - 50) / ringCount;

      html += `
        <circle cx="${cx}" cy="${cy}" r="${r}"
          fill="none"
          stroke="#6C7A96"
          stroke-width="3"
          opacity="0.35"/>
      `;
    }

    html += `
      <text x="${cx}" y="${cy + 5}"
        text-anchor="middle"
        fill="#8892A6"
        font-family="IBM Plex Mono"
        font-size="10">NO DATA</text>
    `;

    svg.innerHTML = html;
    return;
  }

  // Five segmented concentric rings
  for (let ring = 0; ring < ringCount; ring++) {
    const r = 40 + ring * (size / 2 - 50) / ringCount;

    const segRows = activityRows.filter(
      (_, i) => i % ringCount === ring
    );

    const segN = Math.max(segRows.length, 1);

    let angle = ring * 12;
    const step = 360 / segN;

    segRows.forEach(row => {
      const a0 = angle * Math.PI / 180;
      const a1 = (angle + step * 0.75) * Math.PI / 180;

      const x0 = cx + r * Math.cos(a0);
      const y0 = cy + r * Math.sin(a0);

      const x1 = cx + r * Math.cos(a1);
      const y1 = cy + r * Math.sin(a1);

      const large = step * 0.75 > 180 ? 1 : 0;

      const color = colors[row.focus_level] || "#6C7A96";

      const duration = Number(row.duration_min) || 0;
      const application = escapeSvgText(row.application || "Unknown");
      const focusLevel = escapeSvgText(row.focus_level || "Other");

      html += `
        <path
          d="M${x0.toFixed(1)},${y0.toFixed(1)}
             A${r},${r} 0 ${large} 1
             ${x1.toFixed(1)},${y1.toFixed(1)}"
          stroke="${color}"
          stroke-width="4"
          fill="none"
          stroke-linecap="round"
          opacity="0.85">
          <title>${application} — ${duration.toFixed(2)} min — ${focusLevel}</title>
        </path>
      `;

      angle += step;
    });
  }

  // Center detail
  html += `
    <circle cx="${cx}" cy="${cy}"
      r="18"
      fill="none"
      stroke="#232A3B"/>

    <text x="${cx}" y="${cy + 5}"
      text-anchor="middle"
      fill="#8892A6"
      font-family="IBM Plex Mono"
      font-size="10">YOU</text>
  `;

  svg.innerHTML = html;
}




/* ---------------- Timeline ---------------- */
document.addEventListener("click", (e) => {
  if (e.target.classList.contains("filter-pill")) {
    document.querySelectorAll(".filter-pill").forEach(p => p.classList.remove("active"));
    e.target.classList.add("active");
    loadTimeline(e.target.dataset.f);
  }
});

async function loadTimeline(filter) {
  const rows = await fetch(`${API}/api/activity?limit=80&filter=${filter}`).then(x => x.json());
  const list = document.getElementById("timeline-list");
  if (!rows.length) { list.innerHTML = `<p class="empty">No records for this filter yet.</p>`; return; }
  list.innerHTML = rows.slice().reverse().map(r => `
    <div class="tl-item">
      <div class="tl-time mono">${r.timestamp.slice(11, 16)}</div>
      <div class="tl-dot ${r.focus_level}"></div>
      <div>
        <div class="tl-app">${r.application}</div>
        <div class="tl-cat">${r.category}${r.task_difficulty ? " · " + r.task_difficulty + " difficulty" : ""}</div>
      </div>
      <div class="tl-dur">${r.duration_min}m · <span class="pill ${r.focus_level}">${r.focus_level}</span></div>
    </div>`).join("");
}

/* ---------------- Analytics ---------------- */
function destroyChart(id) { if (charts[id]) { charts[id].destroy(); delete charts[id]; } }

function baseChartOpts(extra) {
  return Object.assign({
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#8892A6", font: { family: "Inter", size: 11 } } }, tooltip: { backgroundColor: "#1A2030", titleColor: "#E7EAF2", bodyColor: "#8892A6", borderColor: "#232A3B", borderWidth: 1 } },
    scales: { x: { ticks: { color: "#8892A6", font: { size: 10 } }, grid: { color: "#1A2030" } }, y: { ticks: { color: "#8892A6", font: { size: 10 } }, grid: { color: "#1A2030" } } },
  }, extra || {});
}

async function loadAnalytics() {
  const d = await fetch(`${API}/api/analytics`).then(x => x.json());

  destroyChart("focus-time");
  charts["focus-time"] = new Chart(document.getElementById("chart-focus-time"), {
    type: "line",
    data: { labels: d.focus_over_time.map(x => x.date), datasets: [{ label: "Focus Score %", data: d.focus_over_time.map(x => x.focus_score), borderColor: "#4CD6C0", backgroundColor: "rgba(76,214,192,.12)", fill: true, tension: .35, pointRadius: 5,
pointHoverRadius: 7 }] },
    options: baseChartOpts(),
  });

  destroyChart("distract-time");
  charts["distract-time"] = new Chart(document.getElementById("chart-distract-time"), {
    type: "bar",
    data: { labels: d.distraction_by_time.map(x => x.hour), datasets: [{ label: "Distraction events", data: d.distraction_by_time.map(x => x.events), backgroundColor: "#FF6B6B" }] },
    options: baseChartOpts({ plugins: { legend: { display: false } } }),
  });

  destroyChart("cat-usage");
  const palette = ["#4CD6C0", "#F5B942", "#FF6B6B", "#7C93FF", "#B084F5", "#5EE6D9", "#F58CC0", "#8892A6"];
  charts["cat-usage"] = new Chart(document.getElementById("chart-cat-usage"), {
    type: "doughnut",
    data: { labels: d.category_usage.map(x => x.category), datasets: [{ data: d.category_usage.map(x => x.minutes), backgroundColor: palette, borderColor: "#121620", borderWidth: 2 }] },
    options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "right", labels: { color: "#8892A6", font: { size: 10 }, boxWidth: 10 } } } },
  });

  destroyChart("switch-freq");
  charts["switch-freq"] = new Chart(document.getElementById("chart-switch-freq"), {
    type: "bar",
    data: { labels: d.switching_frequency.map(x => x.date), datasets: [{ label: "Switches", data: d.switching_frequency.map(x => x.switches), backgroundColor: "#7C93FF" }] },
    options: baseChartOpts({ plugins: { legend: { display: false } } }),
  });

  destroyChart("focus-dist");
  charts["focus-dist"] = new Chart(document.getElementById("chart-focus-dist"), {
    type: "bar",
    data: { labels: d.focus_distribution.map(x => x.bucket + " min"), datasets: [{ label: "Sessions", data: d.focus_distribution.map(x => x.count), backgroundColor: "#4CD6C0" }] },
    options: baseChartOpts({ plugins: { legend: { display: false } } }),
  });

  destroyChart("diff-distract");
  charts["diff-distract"] = new Chart(document.getElementById("chart-diff-distract"), {
    type: "bar",
    data: { labels: d.task_vs_distraction.map(x => x.difficulty), datasets: [{ label: "Distraction events", data: d.task_vs_distraction.map(x => x.distractions), backgroundColor: ["#4CD6C0", "#F5B942", "#FF6B6B"] }] },
    options: baseChartOpts({ plugins: { legend: { display: false } } }),
  });

  destroyChart("daily-trend");
  charts["daily-trend"] = new Chart(document.getElementById("chart-daily-trend"), {
    type: "line",
    data: { labels: d.daily_trend.map(x => x.date), datasets: [{ label: "Productivity %", data: d.daily_trend.map(x => x.productivity), borderColor: "#F5B942", backgroundColor: "rgba(245,185,66,.12)", fill: true, tension: .35, pointRadius: 5,
pointHoverRadius: 7 }] },
    options: baseChartOpts(),
  });

  destroyChart("hourly-events");
  charts["hourly-events"] = new Chart(document.getElementById("chart-hourly-events"), {
    type: "bar",
    data: { labels: d.distraction_by_hour.map(x => x.hour + ":00"), datasets: [{ label: "Events", data: d.distraction_by_hour.map(x => x.events), backgroundColor: "#FF6B6B" }] },
    options: baseChartOpts({ plugins: { legend: { display: false } } }),
  });
}

/* ---------------- Prediction ---------------- */

async function loadPrediction() {
  const p = await fetch(`${API}/api/prediction`).then(x => x.json());

  document.getElementById("pred-prob").textContent =
    p.distraction_probability == null
      ? "N/A"
      : p.distraction_probability + "%";

  document.getElementById("pred-window").textContent =
    Array.isArray(p.predicted_window_min)
      ? p.predicted_window_min.join("–") + " min"
      : "Not available";

  document.getElementById("pred-conf").textContent =
    p.confidence == null
      ? "Not yet validated"
      : p.confidence + "%";

  document.getElementById("risk-level-text").textContent =
    p.risk_level;

  document.getElementById("risk-level-text").style.color =
    p.risk_level === "HIGH"
      ? "#FF6B6B"
      : p.risk_level === "MODERATE"
        ? "#F5B942"
        : "#4CD6C0";

  document.getElementById("pred-factors").innerHTML =
    (p.factors || []).map(f => `<li>${f}</li>`).join("");

  drawGauge(p.distraction_probability, p.risk_level);
}


function drawGauge(prob, risk) {
  const svg = document.getElementById("risk-gauge");
  const cx = 110, cy = 110, r = 90;
  const angle = Math.PI * (prob / 100);
  const x = cx - r * Math.cos(angle), y = cy - r * Math.sin(angle);
  const color = risk === "HIGH" ? "#FF6B6B" : risk === "MODERATE" ? "#F5B942" : "#4CD6C0";
  svg.innerHTML = `
    <path d="M20,110 A90,90 0 0 1 200,110" stroke="#232A3B" stroke-width="14" fill="none" stroke-linecap="round"/>
    <path d="M20,110 A90,90 0 0 1 ${x.toFixed(1)},${y.toFixed(1)}" stroke="${color}" stroke-width="14" fill="none" stroke-linecap="round"/>
    <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="7" fill="${color}"/>
    <text x="110" y="105" text-anchor="middle" fill="#E7EAF2" font-family="Space Grotesk" font-size="26" font-weight="700">${prob}%</text>`;
}

/* ---------------- Interventions ---------------- */
async function loadInterventions() {
  const list = await fetch(`${API}/api/interventions`).then(x => x.json());
  const icons = { "Micro Break": "☕", "Focus Sprint": "🎯", "Remove Distraction": "🚫", "Reduce App Switching": "🔀", "Protect Your Risky Hour": "🕙", "Keep Tracking": "⏳", "No Strong Pattern Detected": "✔" };
  document.getElementById("interv-grid").innerHTML = list.map(iv => `
    <div class="interv-card">
      <h4><span>${icons[iv.title] || "✦"}</span> ${iv.title}</h4>
      <p style="margin-top:8px;font-size:13.5px;color:var(--muted);">${iv.description}</p>
      <div class="why">${iv.reason}</div>
    </div>`).join("");
}

/* ---------------- Data collection ---------------- */
async function submitActivity(e) {
  e.preventDefault();
  const payload = {
    application: val("f-app"), category: val("f-cat"), duration_min: parseFloat(val("f-dur")),
    task_type: val("f-task"), task_difficulty: val("f-diff"),
    idle_seconds: parseInt(val("f-idle") || 0), notifications: parseInt(val("f-notif") || 0),
    focus_level: val("f-focus"),
  };
  await fetch(`${API}/api/activity`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  document.getElementById("activity-form").reset();
  document.getElementById("f-dur").value = 15;
  showToast("Activity record added.");
  loadRecords();
  return false;
}
function val(id) { return document.getElementById(id).value; }

async function loadRecords() {
  const rows = await fetch(`${API}/api/activity?limit=30`).then(x => x.json());
  document.getElementById("records-table").innerHTML = rows.slice().reverse().map(r => `
    <tr>
      <td class="mono">${r.timestamp.slice(5, 16).replace("T", " ")}</td>
      <td>${r.application}</td>
      <td>${r.category}</td>
      <td class="mono">${r.duration_min}</td>
      <td><span class="pill ${r.focus_level}">${r.focus_level}</span></td>
    </tr>`).join("");
}

/* ---------------- Hero fingerprint (landing) ---------------- */
function drawHeroFingerprint() {
  const svg = document.getElementById("hero-fingerprint");
  const cx = 190, cy = 190;
  const colors = ["#4CD6C0", "#4CD6C0", "#F5B942", "#FF6B6B", "#4CD6C0"];
  let html = "";
  const rng = mulberry32(7);
  for (let ring = 0; ring < 9; ring++) {
    const r = 40 + ring * 16;
    const segCount = 10 + ring;
    const step = 360 / segCount;
    let angle = ring * 7;
    for (let s = 0; s < segCount; s++) {
      if (rng() < 0.18) { angle += step; continue; } // gap = "distraction" break in the ridge
      const a0 = (angle * Math.PI) / 180, a1 = ((angle + step * 0.72) * Math.PI) / 180;
      const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
      const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
      const large = step * 0.72 > 180 ? 1 : 0;
      const c = colors[ring % colors.length];
      html += `<path d="M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)}" stroke="${c}" stroke-width="2.4" fill="none" stroke-linecap="round" opacity="${0.35 + ring * 0.06}"/>`;
      angle += step;
    }
  }
  html += `<circle cx="${cx}" cy="${cy}" r="26" fill="none" stroke="#232A3B" stroke-width="1.4"/>`;
  html += `<text x="${cx}" y="${cy + 5}" text-anchor="middle" fill="#8892A6" font-family="IBM Plex Mono" font-size="11">FINGERPRINT</text>`;
  svg.innerHTML = html;
}
function mulberry32(a) { return function () { a |= 0; a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }


document.addEventListener("DOMContentLoaded", () => {
  drawHeroFingerprint();
  checkAuthSession();
});


async function checkAuthSession() {
  try {
    const response = await fetch(`${API}/api/auth/me`, {
      credentials: "same-origin"
    });

    if (response.ok) {
      const data = await response.json();

      document.getElementById("dashboard-user-name").textContent =
        data.user.name || "User";

      openDashboard();
    }
  } catch (error) {
    console.log("No active login session.");
  }
}



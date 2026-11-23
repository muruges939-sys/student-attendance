// Only admin / faculty may open this page
const user = getUser();
if (!getToken() || !user || user.role === "STUDENT") {
  logout();
}

const $ = (id) => document.getElementById(id);

function setMsg(text, isError = true) {
  $("att-msg").textContent = text;
  $("att-msg").className = "message " + (isError ? "error" : "ok");
}

function setMsgOn(id, text, isError = true) {
  $(id).textContent = text;
  $(id).className = "message " + (isError ? "error" : "ok");
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "-";
  return td;
}

function today() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 10);
}

// ---------- Overview ----------
async function loadDashboard() {
  const d = (await api("/analytics/dashboard")).data;
  const items = [
    ["Students", d.total_students],
    ["Present", d.today.present],
    ["Half day", d.today.half_day],
    ["Incomplete", d.today.incomplete],
    ["Absent", d.today.absent],
    ["On leave", d.today.on_leave],
    ["Not marked", d.today.not_marked],
    ["Pending leaves", d.pending_leave_requests],
  ];
  if (d.total_faculty !== undefined) items.push(["Faculty", d.total_faculty]);

  $("dash-stats").replaceChildren(...items.map(([label, value]) => {
    const div = document.createElement("div");
    div.className = "stat";
    const b = document.createElement("b");
    b.textContent = value;
    const span = document.createElement("span");
    span.textContent = label;
    div.append(b, span);
    return div;
  }));
}

// ---------- Class attendance ----------
async function loadClassAttendance() {
  setMsg("");
  const date = $("att-date").value;
  const rows = (await api("/class-attendance?date=" + encodeURIComponent(date))).data.students;

  $("att-list").replaceChildren(...rows.map((r) => {
    const tr = document.createElement("tr");

    const tag = document.createElement("span");
    tag.className = "tag " + r.status;
    tag.textContent = r.status;
    const statusTd = document.createElement("td");
    statusTd.append(tag);

    const select = document.createElement("select");
    ["", "PRESENT", "HALF_DAY", "ABSENT", "INCOMPLETE"].forEach((s) => {
      const o = document.createElement("option");
      o.value = s;
      o.textContent = s || "Choose...";
      select.append(o);
    });
    select.addEventListener("change", async () => {
      if (!select.value) return;
      try {
        await api("/class-attendance/student/" + encodeURIComponent(r.student_id), "PUT",
          { date, status: select.value });
        setMsg(`${r.name} marked ${select.value}.`, false);
        await Promise.all([loadClassAttendance(), loadDashboard()]);
      } catch (e) {
        setMsg(e.message);
        select.value = "";
      }
    });
    const actionTd = document.createElement("td");
    actionTd.append(select);

    tr.append(cell(r.student_id), cell(r.name), cell(r.check_in), cell(r.check_out), statusTd, actionTd);
    return tr;
  }));
}

// ---------- Students ----------
let editingId = null;

function resetStudentForm() {
  editingId = null;
  ["st-id", "st-name", "st-email", "st-dept", "st-year", "st-section"].forEach((id) => {
    $(id).value = "";
  });
  $("st-id").disabled = false;
  $("st-save").textContent = "Add student";
  $("st-cancel").classList.add("hidden");
}

function startEdit(s) {
  editingId = s.student_id;
  $("st-id").value = s.student_id;
  $("st-id").disabled = true; // student_id cannot be changed
  $("st-name").value = s.name;
  $("st-email").value = s.email;
  $("st-dept").value = s.department ?? "";
  $("st-year").value = s.year ?? "";
  $("st-section").value = s.section ?? "";
  $("st-save").textContent = "Update student";
  $("st-cancel").classList.remove("hidden");
  $("student-form").scrollIntoView({ behavior: "smooth" });
}

async function loadStudents() {
  const rows = (await api("/students")).data.students;
  $("student-list").replaceChildren(...rows.map((s) => {
    const tr = document.createElement("tr");
    const actionTd = document.createElement("td");

    if (user.role === "ADMIN") {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.className = "small";
      edit.textContent = "Edit";
      edit.addEventListener("click", () => startEdit(s));

      const del = document.createElement("button");
      del.type = "button";
      del.className = "small";
      del.textContent = "Delete";
      del.addEventListener("click", async () => {
        if (!confirm(`Delete ${s.name} (${s.student_id})?`)) return;
        try {
          await api("/students/" + encodeURIComponent(s.student_id), "DELETE");
          setMsgOn("st-msg", "Student deleted.", false);
          if (editingId === s.student_id) resetStudentForm();
          await Promise.all([loadStudents(), loadDashboard(), loadClassAttendance()]);
        } catch (e) {
          setMsgOn("st-msg", e.message);
        }
      });
      actionTd.append(edit, del);
    }

    tr.append(cell(s.student_id), cell(s.name), cell(s.email), cell(s.department),
      cell(s.year), cell(s.section), actionTd);
    return tr;
  }));
}

// ---------- Leave review ----------
async function loadPendingLeaves() {
  const leaves = (await api("/leaves?status=PENDING")).data.leaves;
  $("leave-pending").replaceChildren(...leaves.map((l) => {
    const tr = document.createElement("tr");

    const remarks = document.createElement("input");
    remarks.type = "text";
    remarks.placeholder = "Optional remarks";
    remarks.maxLength = 200;
    const remarksTd = document.createElement("td");
    remarksTd.append(remarks);

    const review = async (decision) => {
      try {
        await api(`/leaves/${l.id}/review`, "PUT", { decision, remarks: remarks.value.trim() });
        setMsgOn("leave-msg", `Leave ${decision.toLowerCase()}.`, false);
        await Promise.all([loadPendingLeaves(), loadDashboard(), loadClassAttendance()]);
      } catch (e) {
        setMsgOn("leave-msg", e.message);
      }
    };

    const approve = document.createElement("button");
    approve.type = "button";
    approve.className = "small";
    approve.textContent = "Approve";
    approve.addEventListener("click", () => review("APPROVED"));

    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "small";
    reject.textContent = "Reject";
    reject.addEventListener("click", () => review("REJECTED"));

    const actionTd = document.createElement("td");
    actionTd.append(approve, reject);

    tr.append(cell(l.student_name + " (" + l.student_id + ")"), cell(l.leave_type),
      cell(l.start_date), cell(l.end_date), cell(l.reason), remarksTd, actionTd);
    return tr;
  }));
}

// ---------- CSV reports ----------
async function downloadCsv(path, filename) {
  const from = $("rep-from").value;
  const to = $("rep-to").value;
  if (!from || !to) return setMsgOn("report-msg", "Choose both From and To dates.");
  setMsgOn("report-msg", "Downloading...", false);
  try {
    const response = await fetch(`${API_BASE}${path}?from=${from}&to=${to}`, {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.message || "Download failed.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${filename}_${from}_to_${to}.csv`;
    document.body.append(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    setMsgOn("report-msg", "Report downloaded.", false);
  } catch (e) {
    setMsgOn("report-msg", e.message);
  }
}

// ---------- Holidays ----------
async function loadHolidays() {
  const rows = (await api("/holidays")).data.holidays;
  $("holiday-list").replaceChildren(...rows.map((h) => {
    const tr = document.createElement("tr");
    const actionTd = document.createElement("td");
    if (user.role === "ADMIN") {
      const del = document.createElement("button");
      del.type = "button";
      del.className = "small";
      del.textContent = "Delete";
      del.addEventListener("click", async () => {
        if (!confirm(`Delete holiday on ${h.holiday_date}?`)) return;
        try {
          await api("/holidays/" + encodeURIComponent(h.holiday_date), "DELETE");
          setMsgOn("holiday-msg", "Holiday deleted.", false);
          await loadHolidays();
        } catch (e) {
          setMsgOn("holiday-msg", e.message);
        }
      });
      actionTd.append(del);
    }
    tr.append(cell(h.holiday_date), cell(h.description), actionTd);
    return tr;
  }));
}

if (user.role === "ADMIN") $("holiday-form").classList.remove("hidden");

$("hol-add").addEventListener("click", async () => {
  const date = $("hol-date").value;
  const description = $("hol-desc").value.trim();
  if (!date || !description) return setMsgOn("holiday-msg", "Enter date and description.");
  try {
    await api("/holidays", "POST", { date, description });
    setMsgOn("holiday-msg", "Holiday added.", false);
    $("hol-desc").value = "";
    await loadHolidays();
  } catch (e) {
    setMsgOn("holiday-msg", e.message);
  }
});

$("rep-att").addEventListener("click", () => downloadCsv("/reports/attendance.csv", "attendance"));
$("rep-sum").addEventListener("click", () => downloadCsv("/reports/summary.csv", "summary"));
$("rep-leave").addEventListener("click", () => downloadCsv("/reports/leaves.csv", "leaves"));

// ---------- Student form (admin only) ----------
if (user.role === "ADMIN") $("student-form").classList.remove("hidden");

$("st-cancel").addEventListener("click", () => {
  resetStudentForm();
  setMsgOn("st-msg", "");
});

$("st-save").addEventListener("click", async () => {
  setMsgOn("st-msg", "");
  const body = {
    name: $("st-name").value.trim(),
    email: $("st-email").value.trim(),
    department: $("st-dept").value.trim(),
    year: Number($("st-year").value),
    section: $("st-section").value.trim(),
  };
  if (!editingId) body.student_id = $("st-id").value.trim();

  if (!body.name || !body.email || !body.department || !body.section || !body.year
      || (!editingId && !body.student_id)) {
    return setMsgOn("st-msg", "Please fill all fields.");
  }

  try {
    if (editingId) {
      await api("/students/" + encodeURIComponent(editingId), "PUT", body);
      setMsgOn("st-msg", "Student updated.", false);
    } else {
      await api("/students", "POST", body);
      setMsgOn("st-msg", "Student added.", false);
    }
    resetStudentForm();
    await Promise.all([loadStudents(), loadDashboard(), loadClassAttendance()]);
  } catch (e) {
    const detail = e.errors ? " " + Object.values(e.errors).join(" ") : "";
    setMsgOn("st-msg", e.message + detail);
  }
});

// ---------- Faculty (admin only) ----------
let editingFacultyId = null;

function resetFacultyForm() {
  editingFacultyId = null;
  ["fc-name", "fc-username", "fc-password", "fc-dept", "fc-year", "fc-section"].forEach((id) => {
    $(id).value = "";
  });
  $("fc-username").disabled = false;
  $("fc-save").textContent = "Add faculty";
  $("fc-cancel").classList.add("hidden");
}

function startFacultyEdit(f) {
  editingFacultyId = f.id;
  $("fc-name").value = f.name;
  $("fc-username").value = f.username;
  $("fc-username").disabled = true; // username cannot be changed here
  $("fc-password").value = "";
  $("fc-password").placeholder = "Leave empty to keep old password";
  $("fc-dept").value = f.department ?? "";
  $("fc-year").value = f.year ?? "";
  $("fc-section").value = f.section ?? "";
  $("fc-save").textContent = "Update faculty";
  $("fc-cancel").classList.remove("hidden");
  $("faculty-panel").scrollIntoView({ behavior: "smooth" });
}

async function loadFaculty() {
  const rows = (await api("/faculty")).data.faculty;
  $("faculty-list").replaceChildren(...rows.map((f) => {
    const tr = document.createElement("tr");

    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "small";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => startFacultyEdit(f));

    const del = document.createElement("button");
    del.type = "button";
    del.className = "small";
    del.textContent = "Delete";
    del.addEventListener("click", async () => {
      if (!confirm(`Delete faculty ${f.name} (${f.username})?`)) return;
      try {
        await api("/faculty/" + f.id, "DELETE");
        setMsgOn("fc-msg", "Faculty deleted.", false);
        if (editingFacultyId === f.id) resetFacultyForm();
        await Promise.all([loadFaculty(), loadDashboard()]);
      } catch (e) {
        setMsgOn("fc-msg", e.message);
      }
    });

    const actionTd = document.createElement("td");
    actionTd.append(edit, del);
    tr.append(cell(f.name), cell(f.username), cell(f.department), cell(f.year), cell(f.section), actionTd);
    return tr;
  }));
}

if (user.role === "ADMIN") $("faculty-panel").classList.remove("hidden");

$("fc-cancel").addEventListener("click", () => {
  resetFacultyForm();
  setMsgOn("fc-msg", "");
});

$("fc-save").addEventListener("click", async () => {
  setMsgOn("fc-msg", "");
  const body = {
    name: $("fc-name").value.trim(),
    department: $("fc-dept").value.trim(),
    year: Number($("fc-year").value),
    section: $("fc-section").value.trim(),
  };
  const password = $("fc-password").value;
  if (password) body.password = password;
  if (!editingFacultyId) body.username = $("fc-username").value.trim();

  if (!body.name || !body.department || !body.section || !body.year
      || (!editingFacultyId && (!body.username || !password))) {
    return setMsgOn("fc-msg", "Please fill all fields (password is required for new faculty).");
  }

  try {
    if (editingFacultyId) {
      await api("/faculty/" + editingFacultyId, "PUT", body);
      setMsgOn("fc-msg", "Faculty updated.", false);
    } else {
      await api("/faculty", "POST", body);
      setMsgOn("fc-msg", "Faculty added.", false);
    }
    resetFacultyForm();
    await Promise.all([loadFaculty(), loadDashboard()]);
  } catch (e) {
    const detail = e.errors ? " " + Object.values(e.errors).join(" ") : "";
    setMsgOn("fc-msg", e.message + detail);
  }
});

// ---------- Start ----------
async function start() {
  $("welcome").textContent = "Welcome, " + user.name;
  $("who").textContent = user.role === "ADMIN"
    ? "Admin"
    : `Faculty | ${user.department} Year ${user.year} Sec ${user.section}`;
  $("att-date").value = today();
  $("rep-to").value = today();
  $("rep-from").value = today().slice(0, 8) + "01";
  try {
    await Promise.all([
      loadDashboard(), loadClassAttendance(), loadStudents(),
      loadPendingLeaves(), loadHolidays(),
    ]);
    if (user.role === "ADMIN") await loadFaculty();
  } catch (e) {
    setMsg(e.message);
  }
}

$("att-load").addEventListener("click", () => loadClassAttendance().catch((e) => setMsg(e.message)));
$("logout").addEventListener("click", logout);
start();
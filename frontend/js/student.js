// Only students may open this page
const user = getUser();
if (!getToken() || !user || user.role !== "STUDENT") {
  logout();
}

const $ = (id) => document.getElementById(id);

function setMessage(text, isError = true) {
  $("action-msg").textContent = text;
  $("action-msg").className = "message " + (isError ? "error" : "ok");
}

// Build text safely (never put server data into innerHTML)
function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "-";
  return td;
}

async function loadToday() {
  const res = await api("/attendance/today");
  const d = res.data;
  const a = d.attendance;

  let text = "Not checked in yet.";
  if (d.holiday) text = "Holiday: " + d.holiday;
  else if (d.on_leave) text = "You are on approved leave today.";
  else if (a && a.check_out) text = `Checked in ${a.check_in}, checked out ${a.check_out}. Status: ${a.status}`;
  else if (a) text = `Checked in at ${a.check_in}. Please check out before leaving.`;
  $("today-status").textContent = text;

  $("btn-in").disabled = !d.can_check_in;
  $("btn-out").disabled = !d.can_check_out;
}

async function loadStats() {
  const s = (await api("/analytics/my")).data;
  const items = [
    ["Attendance %", s.attendance_percentage + "%"],
    ["Present", s.present], ["Half day", s.half_day],
    ["Absent", s.absent], ["Incomplete", s.incomplete],
    ["SL / CL", s.sick_leave + " / " + s.casual_leave],
  ];
  $("stats").replaceChildren(...items.map(([label, value]) => {
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

async function loadHistory() {
  const rows = (await api("/attendance/my")).data.records;
  $("history").replaceChildren(...rows.map((r) => {
    const tr = document.createElement("tr");
    const tag = document.createElement("span");
    tag.className = "tag " + r.status;
    tag.textContent = r.status;
    const statusTd = document.createElement("td");
    statusTd.append(tag);
    tr.append(cell(r.attendance_date), cell(r.check_in), cell(r.check_out), statusTd);
    return tr;
  }));
}

async function loadNotifications() {
  const list = (await api("/notifications")).data.notifications;
  $("notif-list").replaceChildren(...list.map((n) => {
    const li = document.createElement("li");
    if (!n.is_read) li.className = "unread";
    li.textContent = n.title;
    const small = document.createElement("small");
    small.textContent = n.message;
    li.append(small);
    li.addEventListener("click", async () => {
      if (n.is_read) return;
      await api(`/notifications/${n.id}/read`, "PUT");
      loadNotifications();
    });
    return li;
  }));
  const unread = (await api("/notifications/unread-count")).data.unread;
  $("unread").textContent = unread;
  $("unread").classList.toggle("hidden", unread === 0);
}
function setLeaveMsg(text, isError = true) {
  $("leave-msg").textContent = text;
  $("leave-msg").className = "message " + (isError ? "error" : "ok");
}

async function loadLeaves() {
  const leaves = (await api("/leaves/my")).data.leaves;
  $("leave-list").replaceChildren(...leaves.map((l) => {
    const tr = document.createElement("tr");
    const tag = document.createElement("span");
    tag.className = "tag " + l.status;
    tag.textContent = l.status;
    const statusTd = document.createElement("td");
    statusTd.append(tag);

    const actionTd = document.createElement("td");
    if (l.status === "PENDING") {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "small";
      btn.textContent = "Cancel";
      btn.addEventListener("click", async () => {
        try {
          await api(`/leaves/${l.id}/cancel`, "PUT");
          setLeaveMsg("Leave request cancelled.", false);
          await loadLeaves();
        } catch (e) {
          setLeaveMsg(e.message);
        }
      });
      actionTd.append(btn);
    }
    tr.append(cell(l.leave_type), cell(l.start_date), cell(l.end_date), statusTd, cell(l.remarks), actionTd);
    return tr;
  }));
}

$("leave-submit").addEventListener("click", async () => {
  setLeaveMsg("");
  const body = {
    leave_type: $("leave-type").value,
    start_date: $("leave-start").value,
    end_date: $("leave-end").value,
    reason: $("leave-reason").value.trim(),
  };
  if (!body.start_date || !body.end_date || !body.reason) {
    return setLeaveMsg("Please fill start date, end date and reason.");
  }
  try {
    await api("/leaves", "POST", body);
    setLeaveMsg("Leave request submitted.", false);
    $("leave-reason").value = "";
    await loadLeaves();
  } catch (e) {
    const detail = e.errors ? " " + Object.values(e.errors).join(" ") : "";
    setLeaveMsg(e.message + detail);
  }
});

async function refreshAll() {
  try {
        await Promise.all([loadToday(), loadStats(), loadHistory(), loadNotifications(), loadLeaves()]);
  } catch (e) {
    setMessage(e.message);
  }
}

async function doAction(path, successText) {
  setMessage("");
  try {
    await api(path, "POST");
    setMessage(successText, false);
    await refreshAll();
  } catch (e) {
    setMessage(e.message);
  }
}

$("btn-in").addEventListener("click", () => doAction("/attendance/check-in", "Checked in successfully."));
$("btn-out").addEventListener("click", () => doAction("/attendance/check-out", "Checked out successfully."));
$("logout").addEventListener("click", logout);
$("mark-all").addEventListener("click", async () => {
  await api("/notifications/read-all", "PUT");
  loadNotifications();
});

$("welcome").textContent = "Welcome, " + user.name;
$("who").textContent = `${user.student_id} | ${user.department} Year ${user.year} Sec ${user.section}`;
refreshAll();
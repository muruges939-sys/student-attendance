const message = document.getElementById("message");

function showMessage(text, isError = true) {
  message.textContent = text;
  message.className = "message " + (isError ? "error" : "ok");
}

function showTab(name) {
  const student = name === "student";
  document.getElementById("student-box").classList.toggle("hidden", !student);
  document.getElementById("staff-box").classList.toggle("hidden", student);
  document.getElementById("tab-student").classList.toggle("active", student);
  document.getElementById("tab-staff").classList.toggle("active", !student);
  showMessage("");
}

function goToDashboard(user) {
  // These dashboard pages are built in the next steps
  window.location.href = user.role === "STUDENT" ? "student.html" : "staff.html";
}

document.getElementById("tab-student").addEventListener("click", () => showTab("student"));
document.getElementById("tab-staff").addEventListener("click", () => showTab("staff"));

document.getElementById("student-login").addEventListener("click", async () => {
  const email = document.getElementById("email").value.trim();
  if (!email) return showMessage("Please enter your email.");
  try {
    const res = await api("/auth/student-dev-login", "POST", { email });
    saveSession(res.data.token, res.data.user);
    goToDashboard(res.data.user);
  } catch (e) {
    showMessage(e.message);
  }
});

document.getElementById("staff-login").addEventListener("click", async () => {
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  if (!username || !password) return showMessage("Enter username and password.");
  try {
    const res = await api("/auth/login", "POST", { username, password });
    saveSession(res.data.token, res.data.user);
    goToDashboard(res.data.user);
  } catch (e) {
    showMessage(e.message);
  }
});
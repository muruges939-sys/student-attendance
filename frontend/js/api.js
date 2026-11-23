const API_BASE = "http://127.0.0.1:5000/api";

function getToken() {
  return sessionStorage.getItem("token");
}

function getUser() {
  const u = sessionStorage.getItem("user");
  return u ? JSON.parse(u) : null;
}

function saveSession(token, user) {
  sessionStorage.setItem("token", token);
  sessionStorage.setItem("user", JSON.stringify(user));
}

function logout() {
  sessionStorage.clear();
  window.location.href = "index.html";
}

async function api(path, method = "GET", body = null) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const response = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });
  const data = await response.json();

  if (response.status === 401 && token) {
    logout(); // token expired or invalid
  }
  if (!data.success) {
    const err = new Error(data.message || "Request failed");
    err.errors = data.errors;
    throw err;
  }
  return data;
}
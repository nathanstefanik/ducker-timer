document.getElementById("new-timer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fields = Object.fromEntries(
    ["h", "m", "s"].map((k) => [k, document.getElementById(k).value || "0"]));
  fields.title = document.getElementById("title").value.trim();
  fields.names = document.getElementById("names").value
    .split("\n").map((n) => n.trim()).filter(Boolean);
  fields.dist = document.querySelector('input[name="dist"]:checked').value;
  const resp = await fetch("/api/new", {method: "POST", body: JSON.stringify(fields)});
  const data = await resp.json();
  if (resp.ok) location.href = `/t/${data.code}#${data.token}`;
  else document.getElementById("error").textContent = data.error;
});

const ENDPOINT = "http://127.0.0.1:48217/presence";

function post(body) {
  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-YT-Presence": "1" },
    body: JSON.stringify(body),
  }).catch(() => {});
}

chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.tab) {
    post({ ...message, tabId: sender.tab.id });
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  post({ tabId, gone: true });
});

const ENDPOINT = "http://127.0.0.1:48217/presence"; // must match EXTENSION_PORT in youtube-presence.pyw

function post(body) {
  fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-YT-Presence": "1" },
    body: JSON.stringify(body),
  }).catch(() => {});
}

// Content script fetches follow the page's CORS rules, so relay their state from here tagged with the tab id
chrome.runtime.onMessage.addListener((message, sender) => {
  if (sender.tab) {
    post({ ...message, tabId: sender.tab.id });
  }
});

// The page's own "gone" may not get out while the tab closes, so report the close from here
chrome.tabs.onRemoved.addListener((tabId) => {
  post({ tabId, gone: true });
});

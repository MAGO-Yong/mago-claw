/**
 * LOBI 评测辅助脚本
 * 用于在 LOBI iframe 中执行点击、输入等操作
 */

const ws = require('/app/node_modules/.pnpm/ws@8.19.0/node_modules/ws');

const PAGE_TARGET = '492D87CA0397DCD7489FA9CE18B5E4F0';
const IFRAME_FRAME_ID = '1CD63DF9F6300709AC4917429C8CF757';
const WS_URL = `ws://127.0.0.1:18800/devtools/page/${PAGE_TARGET}`;

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function createClient() {
  return new Promise((resolve, reject) => {
    const client = new ws(WS_URL);
    client.on('open', () => resolve(client));
    client.on('error', reject);
    setTimeout(() => reject(new Error('Connect timeout')), 5000);
  });
}

async function getFrameCtx(client) {
  return new Promise((resolve, reject) => {
    let id = Math.floor(Math.random() * 10000);
    const handler = (data) => {
      const msg = JSON.parse(data);
      if (msg.id === id && msg.result && msg.result.executionContextId) {
        client.off('message', handler);
        resolve(msg.result.executionContextId);
      }
    };
    client.on('message', handler);
    client.send(JSON.stringify({
      id,
      method: 'Page.createIsolatedWorld',
      params: { frameId: IFRAME_FRAME_ID, worldName: 'eval_' + id, grantUniveralAccess: true }
    }));
    setTimeout(() => reject(new Error('getFrameCtx timeout')), 5000);
  });
}

async function evalInFrame(client, ctxId, code) {
  return new Promise((resolve, reject) => {
    let id = Math.floor(Math.random() * 10000);
    const handler = (data) => {
      const msg = JSON.parse(data);
      if (msg.id === id) {
        client.off('message', handler);
        if (msg.result && msg.result.result) {
          resolve(msg.result.result.value);
        } else {
          reject(new Error('Eval failed: ' + JSON.stringify(msg)));
        }
      }
    };
    client.on('message', handler);
    client.send(JSON.stringify({
      id,
      method: 'Runtime.evaluate',
      params: { expression: code, contextId: ctxId }
    }));
    setTimeout(() => reject(new Error('evalInFrame timeout')), 10000);
  });
}

async function clickNewSession() {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    const result = await evalInFrame(client, ctxId,
      'var btn = Array.from(document.querySelectorAll("button")).find(b => b.textContent.trim() === "New session"); if (btn) { btn.click(); "Clicked"; } else { "Not found"; }'
    );
    console.log('clickNewSession:', result);
    return result === 'Clicked';
  } finally {
    client.close();
  }
}

async function typeInInput(text) {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    
    // Focus on the textarea
    await evalInFrame(client, ctxId,
      'var ta = document.querySelector("textarea"); if (ta) { ta.focus(); ta.click(); "focused"; } else { "no textarea"; }'
    );
    
    await sleep(200);
    
    // Clear and set value
    const result = await evalInFrame(client, ctxId, `
      var ta = document.querySelector("textarea");
      if (ta) {
        ta.focus();
        // Use React's synthetic event system
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        nativeInputValueSetter.call(ta, ${JSON.stringify(text)});
        ta.dispatchEvent(new Event('input', { bubbles: true }));
        ta.dispatchEvent(new Event('change', { bubbles: true }));
        "typed: " + ta.value.substr(0, 30);
      } else { "no textarea"; }
    `);
    
    console.log('typeInInput:', result);
    return result;
  } finally {
    client.close();
  }
}

async function clickSend() {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    const result = await evalInFrame(client, ctxId,
      'var btn = Array.from(document.querySelectorAll("button")).find(b => b.textContent.trim().includes("Send") || b.textContent.trim().includes("Queue")); if (btn) { btn.click(); "Clicked: " + btn.textContent.trim(); } else { var btns = Array.from(document.querySelectorAll("button")).map(b => b.textContent.trim()); "Not found, btns: " + btns.join("|"); }'
    );
    console.log('clickSend:', result);
    return result;
  } finally {
    client.close();
  }
}

async function pressEnter() {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    const result = await evalInFrame(client, ctxId,
      'var ta = document.querySelector("textarea"); if (ta) { ta.focus(); var e = new KeyboardEvent("keydown", {bubbles:true, cancelable:true, key:"Enter", code:"Enter", keyCode:13}); ta.dispatchEvent(e); "pressed"; } else { "no textarea"; }'
    );
    console.log('pressEnter:', result);
    return result;
  } finally {
    client.close();
  }
}

async function getLastMessage() {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    const result = await evalInFrame(client, ctxId, `
      var msgs = document.querySelectorAll('[data-role="assistant"]');
      if (msgs.length === 0) {
        // Try different selectors
        var allMsgs = Array.from(document.querySelectorAll('.message, [class*="message"], [class*="chat"]'));
        "count: " + allMsgs.length;
      } else {
        msgs[msgs.length - 1].textContent.trim().substr(0, 200);
      }
    `);
    console.log('getLastMessage:', result);
    return result;
  } finally {
    client.close();
  }
}

async function isResponseComplete() {
  const client = await createClient();
  try {
    const ctxId = await getFrameCtx(client);
    // Check if there's a Stop button (response in progress) or Queue/Send (ready for input)
    const result = await evalInFrame(client, ctxId,
      'var stopBtn = Array.from(document.querySelectorAll("button")).find(b => b.textContent.trim() === "Stop"); stopBtn ? "in_progress" : "complete";'
    );
    return result === 'complete';
  } finally {
    client.close();
  }
}

// Main operations
const action = process.argv[2];
const arg = process.argv[3];

async function main() {
  switch (action) {
    case 'new-session':
      await clickNewSession();
      break;
    case 'type':
      await typeInInput(arg || '');
      break;
    case 'send':
      await clickSend();
      break;
    case 'enter':
      await pressEnter();
      break;
    case 'check-complete':
      const done = await isResponseComplete();
      console.log(done ? 'COMPLETE' : 'IN_PROGRESS');
      break;
    case 'get-message':
      await getLastMessage();
      break;
    default:
      console.log('Usage: node lobi-eval-helper.js [new-session|type|send|enter|check-complete|get-message] [args]');
  }
}

main().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});

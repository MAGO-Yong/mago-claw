/**
 * LOBI 评测主脚本
 * 通过 CDP iframe isolated world 操作 LOBI 进行评测
 */

const ws = require('/app/node_modules/.pnpm/ws@8.19.0/node_modules/ws');

const PAGE_TARGET = '492D87CA0397DCD7489FA9CE18B5E4F0';
let IFRAME_FRAME_ID = '1CD63DF9F6300709AC4917429C8CF757';
const WS_URL = `ws://127.0.0.1:18800/devtools/page/${PAGE_TARGET}`;

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// Keep a persistent connection
let globalClient = null;
let msgId = 1000;

async function ensureClient() {
  if (globalClient && globalClient.readyState === 1) return globalClient;
  
  return new Promise((resolve, reject) => {
    const client = new ws(WS_URL);
    client.on('open', () => {
      globalClient = client;
      resolve(client);
    });
    client.on('close', () => { globalClient = null; });
    client.on('error', reject);
    setTimeout(() => reject(new Error('Connect timeout')), 5000);
  });
}

async function cdpSend(method, params = {}) {
  const client = await ensureClient();
  const id = ++msgId;
  return new Promise((resolve, reject) => {
    const handler = (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.id === id) {
        client.off('message', handler);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };
    client.on('message', handler);
    client.send(JSON.stringify({ id, method, params }));
    setTimeout(() => {
      client.off('message', handler);
      reject(new Error(`CDP timeout: ${method}`));
    }, 15000);
  });
}

async function updateFrameId() {
  const result = await cdpSend('Page.getFrameTree');
  const children = result.frameTree.childFrames || [];
  if (children.length > 0) {
    IFRAME_FRAME_ID = children[0].frame.id;
    console.log('[frame] Updated frame ID:', IFRAME_FRAME_ID);
  }
}

async function getIframeCtx() {
  const result = await cdpSend('Page.createIsolatedWorld', {
    frameId: IFRAME_FRAME_ID,
    worldName: 'eval_' + Date.now(),
    grantUniveralAccess: true
  });
  return result.executionContextId;
}

async function evalInIframe(code) {
  const ctxId = await getIframeCtx();
  const result = await cdpSend('Runtime.evaluate', {
    expression: code,
    contextId: ctxId,
    returnByValue: true,
    awaitPromise: false
  });
  return result.result ? result.result.value : undefined;
}

async function clickNewSession() {
  const result = await evalInIframe(`
    (function() {
      var btn = Array.from(document.querySelectorAll("button")).find(b => b.textContent.trim() === "New session");
      if (btn) { btn.click(); return "Clicked"; }
      var btns = Array.from(document.querySelectorAll("button")).map(b => b.textContent.trim().substr(0, 20));
      return "Not found, buttons: " + btns.slice(-5).join("|");
    })()
  `);
  console.log('[new-session]', result);
  return result === 'Clicked';
}

async function typeQuestion(text) {
  // First focus on textarea
  await evalInIframe(`
    (function() {
      var ta = document.querySelector("textarea");
      if (ta) { ta.focus(); return "focused"; }
      return "no textarea";
    })()
  `);
  
  await sleep(300);
  
  // Set the value using React's mechanism
  const result = await evalInIframe(`
    (function() {
      var ta = document.querySelector("textarea");
      if (!ta) return "no textarea";
      ta.focus();
      // Simulate typing by setting value and firing events
      var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
      nativeInputValueSetter.call(ta, ${JSON.stringify(text)});
      ta.dispatchEvent(new Event('input', { bubbles: true }));
      ta.dispatchEvent(new Event('change', { bubbles: true }));
      return "typed " + ta.value.length + " chars";
    })()
  `);
  console.log('[type]', result);
  return result;
}

async function clickSendButton() {
  const result = await evalInIframe(`
    (function() {
      var btns = Array.from(document.querySelectorAll("button"));
      // Send button text may be "Send" with icon
      var sendBtn = btns.find(b => {
        var t = b.textContent.trim();
        return t === "Send" || t === "Send↵" || t.startsWith("Send");
      });
      if (sendBtn && !sendBtn.disabled) {
        sendBtn.click();
        return "Sent";
      }
      // Try Queue button
      var queueBtn = btns.find(b => b.textContent.trim().includes("Queue"));
      if (queueBtn) { queueBtn.click(); return "Queued"; }
      return "Not found: " + btns.map(b => b.textContent.trim().substr(0,15)).slice(-5).join("|");
    })()
  `);
  console.log('[send]', result);
  return result;
}

async function isComplete() {
  try {
    const result = await evalInIframe(`
      (function() {
        var btns = Array.from(document.querySelectorAll("button")).map(b => b.textContent.trim());
        var hasStop = btns.some(t => t === "Stop");
        var hasSend = btns.some(t => t.includes("Send") || t.includes("Queue"));
        return JSON.stringify({hasStop, hasSend, btns: btns.slice(-5)});
      })()
    `);
    const info = JSON.parse(result);
    return !info.hasStop;
  } catch(e) {
    return false;
  }
}

async function waitForComplete(timeoutMs = 480000) { // 8 min timeout
  const start = Date.now();
  let lastCheck = '';
  let stableCount = 0;
  
  while (Date.now() - start < timeoutMs) {
    await sleep(3000);
    const done = await isComplete();
    if (done) {
      // Wait a bit more to ensure stable
      await sleep(2000);
      const done2 = await isComplete();
      if (done2) {
        return { timeout: false, elapsed: Math.round((Date.now() - start) / 1000) };
      }
    }
    
    // Log progress every 15s
    if ((Date.now() - start) % 15000 < 3000) {
      console.log(`[wait] ${Math.round((Date.now() - start)/1000)}s elapsed, in_progress...`);
    }
  }
  
  return { timeout: true, elapsed: Math.round((Date.now() - start) / 1000) };
}

async function getResponseContent() {
  const result = await evalInIframe(`
    (function() {
      // Get all message containers
      var log = document.querySelector('[role="log"]');
      if (!log) return "no log found";
      
      var messages = Array.from(log.children);
      var lastAssistant = null;
      
      // Find the last assistant message
      for (var i = messages.length - 1; i >= 0; i--) {
        var msg = messages[i];
        // Check if it has "A" avatar (assistant)
        var avatar = msg.querySelector('[class*="avatar"]') || msg.children[0];
        var text = avatar ? avatar.textContent.trim() : '';
        if (text === 'A' || msg.textContent.includes('Assistant')) {
          lastAssistant = msg;
          break;
        }
      }
      
      if (!lastAssistant) {
        // Just get last message
        lastAssistant = messages[messages.length - 1];
      }
      
      if (!lastAssistant) return "no messages";
      
      var content = lastAssistant.textContent.trim();
      return content.substr(0, 2000);
    })()
  `);
  return result || '';
}

async function getToolCalls() {
  const result = await evalInIframe(`
    (function() {
      // Find all tool call buttons (skill calls)
      var toolBtns = Array.from(document.querySelectorAll('button[class*="tool"], button')).filter(b => {
        var t = b.textContent;
        return t.includes('Exec') || t.includes('Read') || (b.className && b.className.includes('tool'));
      });
      
      // Also check for tool messages
      var toolMsgs = Array.from(document.querySelectorAll('[class*="tool-call"], [class*="toolCall"]'));
      
      // Get skill names from button text
      var skills = new Set();
      
      // Look for buttons containing skill names
      var allBtns = document.querySelectorAll('button');
      Array.from(allBtns).forEach(btn => {
        var txt = btn.textContent;
        if (txt.includes('xray') || txt.includes('alarm') || txt.includes('service-tree') || 
            txt.includes('metrics') || txt.includes('Exec') || txt.includes('Read')) {
          skills.add(txt.trim().substr(0, 80));
        }
      });
      
      return JSON.stringify(Array.from(skills).slice(0, 10));
    })()
  `);
  try {
    return JSON.parse(result) || [];
  } catch(e) {
    return [];
  }
}

async function getLastAssistantMessage() {
  const result = await evalInIframe(`
    (function() {
      // Get last assistant message content
      var all = document.querySelectorAll('*');
      var assistantTexts = [];
      
      for (var el of all) {
        if (el.children.length === 0) { // leaf nodes
          var t = el.textContent.trim();
          if (t.length > 20 && t.length < 5000) {
            var parent = el;
            var isAssistant = false;
            while (parent) {
              if (parent.className && (parent.className.includes('assistant') || parent.className.includes('message'))) {
                isAssistant = true;
                break;
              }
              parent = parent.parentElement;
            }
          }
        }
      }
      
      // Simpler: get all text from the last message block that's not a tool call
      var log = document.querySelector('[role="log"]');
      if (!log) return "no log";
      
      var blocks = Array.from(log.children);
      var lastBlock = blocks[blocks.length - 1];
      if (!lastBlock) return "no blocks";
      
      // Get paragraphs and headings
      var textEls = lastBlock.querySelectorAll('p, h1, h2, h3, li, td, th');
      var texts = Array.from(textEls).map(el => el.textContent.trim()).filter(t => t.length > 0);
      return texts.slice(0, 30).join(' | ');
    })()
  `);
  return result || '';
}

// Main evaluation function
async function runQuestion(qNum, question) {
  console.log(`\n=== Q${qNum} START ===`);
  const startTime = new Date();
  const startHH = startTime.toTimeString().substr(0, 5);
  
  // Update frame ID in case it changed
  await updateFrameId();
  
  // Click New Session
  console.log('[Q' + qNum + '] Clicking New session...');
  const clicked = await clickNewSession();
  if (!clicked) {
    console.error('[Q' + qNum + '] Failed to click New session!');
  }
  
  // Wait for page to reset
  await sleep(3000);
  
  // Type the question
  console.log('[Q' + qNum + '] Typing question...');
  await typeQuestion(question);
  await sleep(1000);
  
  // Click Send
  console.log('[Q' + qNum + '] Clicking Send...');
  const sent = await clickSendButton();
  
  if (!sent.includes('Sent') && !sent.includes('Queue')) {
    // Try pressing Enter as backup
    console.log('[Q' + qNum + '] Send failed, trying keyboard...');
    await evalInIframe(`
      (function() {
        var ta = document.querySelector("textarea");
        if (ta) {
          ta.focus();
          var e = new KeyboardEvent("keydown", {bubbles:true, cancelable:true, key:"Enter", code:"Enter", keyCode:13});
          ta.dispatchEvent(e);
          return "Enter pressed";
        }
        return "no textarea";
      })()
    `);
  }
  
  console.log('[Q' + qNum + '] Waiting for response...');
  const waitResult = await waitForComplete(480000);
  
  const endTime = new Date();
  const elapsedSec = Math.round((endTime - startTime) / 1000);
  const endHH = endTime.toTimeString().substr(0, 5);
  
  console.log(`[Q${qNum}] Done! Elapsed: ${elapsedSec}s, Timeout: ${waitResult.timeout}`);
  
  // Get response content
  const responseText = await getLastAssistantMessage();
  const toolCalls = await getToolCalls();
  
  return {
    qNum,
    question,
    startTime: startHH,
    endTime: endHH,
    elapsed: waitResult.timeout ? 'TIMEOUT' : `${elapsedSec}s`,
    timeout: waitResult.timeout,
    responseText,
    toolCalls
  };
}

// Export for use
module.exports = { runQuestion, evalInIframe, clickNewSession, typeQuestion, clickSendButton, waitForComplete, isComplete, getLastAssistantMessage, getToolCalls, updateFrameId, sleep };

// CLI interface
if (require.main === module) {
  const action = process.argv[2];
  
  (async () => {
    await updateFrameId();
    
    if (action === 'test') {
      // Test basic operations
      console.log('Testing isComplete...');
      const done = await isComplete();
      console.log('isComplete:', done);
      
      console.log('Getting last message...');
      const msg = await getLastAssistantMessage();
      console.log('Last message:', msg.substr(0, 200));
    }
    
    process.exit(0);
  })().catch(e => {
    console.error('Fatal:', e);
    process.exit(1);
  });
}

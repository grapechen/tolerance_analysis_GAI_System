const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const http = require('http');

let mainWindow;
let flaskProcess;
const FLASK_PORT = 7011;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;

// ── 找 Flask 可執行檔 ────────────────────────────────────────────
function getFlaskCmd() {
  if (app.isPackaged) {
    // 打包後：使用 PyInstaller 產出的 exe
    const exePath = path.join(process.resourcesPath, 'server', 'ai_app.exe');
    return { cmd: exePath, args: [], cwd: path.join(process.resourcesPath, 'server') };
  } else {
    // 開發時：直接用 python
    const serverDir = path.join(__dirname, '..', 'server');
    return { cmd: 'python', args: ['ai_app.py'], cwd: serverDir };
  }
}

// ── 啟動 Flask ────────────────────────────────────────────────────
function startFlask() {
  const { cmd, args, cwd } = getFlaskCmd();
  flaskProcess = spawn(cmd, args, {
    cwd,
    env: { ...process.env },
    windowsHide: true,   // 不顯示黑色命令提示字元視窗
  });
  flaskProcess.stdout.on('data', (d) => console.log('[Flask]', d.toString().trim()));
  flaskProcess.stderr.on('data', (d) => console.error('[Flask]', d.toString().trim()));
  flaskProcess.on('close', (code) => console.log(`[Flask] 已結束，代碼: ${code}`));
}

// ── 等待 Flask 就緒（最多等 30 秒）──────────────────────────────
function waitForFlask(maxRetries = 30) {
  return new Promise((resolve, reject) => {
    let retries = 0;
    const check = () => {
      http.get(FLASK_URL, () => resolve())
        .on('error', () => {
          if (++retries >= maxRetries) {
            reject(new Error('Flask 啟動逾時，請重新開啟程式'));
          } else {
            setTimeout(check, 1000);
          }
        });
    };
    check();
  });
}

// ── 載入畫面 HTML ────────────────────────────────────────────────
const LOADING_HTML = `data:text/html;charset=utf-8,
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  body {
    margin: 0;
    background: #0f172a;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    font-family: "Microsoft JhengHei", sans-serif;
    color: #e2e8f0;
  }
  .spinner {
    width: 48px; height: 48px;
    border: 4px solid #334155;
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 1s linear infinite;
    margin-bottom: 24px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  h2 { margin: 0 0 8px; font-size: 1.4rem; }
  p  { margin: 0; color: #94a3b8; font-size: 0.9rem; }
</style>
</head>
<body>
  <div class="spinner"></div>
  <h2>公差 AI 助手啟動中</h2>
  <p>正在載入 AI 引擎，請稍候...</p>
</body>
</html>`;

const ERROR_HTML = (msg) => `data:text/html;charset=utf-8,
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
  body {
    margin: 0; background: #0f172a;
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 100vh;
    font-family: "Microsoft JhengHei", sans-serif;
    color: #e2e8f0;
  }
  h2 { color: #f87171; }
  p  { color: #94a3b8; }
</style>
</head>
<body>
  <h2>啟動失敗</h2>
  <p>${msg}</p>
  <p>請關閉後重新開啟程式，或聯絡管理員。</p>
</body>
</html>`;

// ── 建立主視窗 ────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 600,
    title: '公差 AI 助手',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
    show: false,
  });

  mainWindow.loadURL(LOADING_HTML);
  mainWindow.once('ready-to-show', () => mainWindow.show());

  waitForFlask()
    .then(() => mainWindow.loadURL(FLASK_URL))
    .catch((err) => {
      console.error(err);
      mainWindow.loadURL(ERROR_HTML(err.message));
    });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── 生命週期 ───────────────────────────────────────────────────────
app.whenReady().then(() => {
  startFlask();
  createWindow();
});

app.on('window-all-closed', () => {
  if (flaskProcess) {
    flaskProcess.kill();
    flaskProcess = null;
  }
  app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) createWindow();
});

from html import escape

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.auth import _TOKEN
from app.services.sources import get_fonte

router = APIRouter(include_in_schema=False)

_HTML = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CPF Validador</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🔍</text></svg>">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #0d1117;
      --surface: #161b22;
      --surface2: #1c2128;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #7d8590;
      --accent: #1f6feb;
      --accent-h: #388bfd;
      --ok-bg: rgba(255,255,255,.05);
      --ok-text: #7d8590;
      --err-bg: rgba(255,255,255,.04);
      --err-text: #7d8590;
      --r: 10px;
    }

    body {
      font-family: 'Inter', system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 48px 20px 80px;
    }

    .logo { font-size: 28px; margin-bottom: 6px; }

    h1 {
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -.3px;
      margin-bottom: 6px;
      text-align: center;
    }

    .sub { font-size: 13px; color: var(--muted); margin-bottom: 28px; text-align: center; }

    #main-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
    }

    .wrap { width: 100%; max-width: 460px; }

    /* ── tabs ── */
    .tabs {
      display: flex;
      gap: 4px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 4px;
      margin-bottom: 14px;
    }

    .tab {
      flex: 1;
      text-align: center;
      padding: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      border-radius: 7px;
      cursor: pointer;
      transition: background .15s, color .15s;
      user-select: none;
    }

    .tab.active {
      background: var(--surface2);
      color: var(--text);
    }

    .tab-panel { display: none; }
    .tab-panel.active { display: block; }

    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 26px 26px 22px;
    }

    .field + .field { margin-top: 15px; }

    label {
      display: block;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
      margin-bottom: 7px;
    }

    input {
      width: 100%;
      background: var(--bg);
      border: 1px solid var(--border);
      border-radius: 7px;
      padding: 11px 14px;
      color: var(--text);
      font-size: 15px;
      font-family: inherit;
      outline: none;
      transition: border-color .15s, box-shadow .15s;
    }

    input:focus {
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(31,111,235,.15);
    }

    input::placeholder { color: var(--muted); }

    .hint { margin-top: 5px; font-size: 12px; color: var(--muted); }
    .hint code {
      background: var(--surface2);
      border: 1px solid var(--border);
      border-radius: 4px;
      padding: 1px 5px;
      font-size: 11px;
    }

    button {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      width: 100%;
      background: var(--accent);
      color: #fff;
      border: none;
      border-radius: 7px;
      padding: 12px;
      font-size: 14px;
      font-weight: 600;
      font-family: inherit;
      cursor: pointer;
      margin-top: 20px;
      transition: background .15s;
    }

    button:hover:not(:disabled) { background: var(--accent-h); }
    button:disabled { opacity: .5; cursor: not-allowed; }

    /* ── log ── */
    .log-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 16px 20px;
      margin-top: 14px;
    }

    .log-head {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .07em;
      color: var(--muted);
      margin-bottom: 12px;
      display: flex;
      justify-content: space-between;
    }

    .elapsed { font-variant-numeric: tabular-nums; }

    .step {
      display: flex;
      align-items: flex-start;
      gap: 10px;
      font-size: 13px;
      padding: 4px 0;
      opacity: 0;
      transform: translateY(4px);
      transition: opacity .2s, transform .2s;
      line-height: 1.4;
    }

    .step.show { opacity: 1; transform: none; }

    .si {
      flex-shrink: 0;
      width: 18px; height: 20px;
      display: flex; align-items: center; justify-content: center;
    }

    .step.pending .si::after {
      content: '';
      display: block;
      width: 13px; height: 13px;
      border: 2px solid var(--border);
      border-top-color: var(--accent);
      border-radius: 50%;
      animation: rot .6s linear infinite;
    }

    .step.done .si { color: var(--muted); }
    .step.done .si::after { content: '✓'; font-size: 14px; }
    .step.done > span:last-child { color: var(--muted); }

    .step.fail .si { color: var(--muted); }
    .step.fail .si::after { content: '✕'; font-size: 14px; }
    .step.fail > span:last-child { color: var(--muted); }

    @keyframes rot { to { transform: rotate(360deg); } }

    /* ── result card ── */
    .result-card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      overflow: hidden;
      margin-top: 14px;
    }

    .result-card--mismatch {
      border-color: #f0883e;
      border-left: 3px solid #f0883e;
      background: rgba(240, 136, 62, 0.04);
    }

    .result-head {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 16px 10px;
      border-bottom: 1px solid var(--border);
    }

    .result-name { font-weight: 700; font-size: 15px; flex: 1; min-width: 0; }
    .result-indicator { white-space: nowrap; flex-shrink: 0; padding-top: 2px; }

    .result-body { padding: 2px 16px 10px; }

    .result-card + .result-card { margin-top: 8px; }

    .row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 7px 0;
      font-size: 13px;
      border-bottom: 1px solid var(--border);
      gap: 12px;
    }

    .row:last-child { border-bottom: none; }
    .row-l { color: var(--muted); white-space: nowrap; }
    .row-v { font-weight: 500; text-align: right; font-variant-numeric: tabular-nums; }

    .meta { font-size: 12px; color: var(--muted); margin-top: 10px; padding: 0 2px; display: flex; gap: 16px; flex-wrap: wrap; }

    /* ── history ── */
    .hist-empty {
      text-align: center;
      color: var(--muted);
      font-size: 13px;
      padding: 32px 0;
    }

    .hist-actions {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }

    .toggle-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--muted);
      user-select: none;
      cursor: pointer;
    }

    .toggle {
      position: relative;
      width: 32px;
      height: 18px;
      flex-shrink: 0;
    }

    .toggle input { display: none; }

    .toggle-track {
      position: absolute;
      inset: 0;
      background: var(--border);
      border-radius: 9px;
      transition: background .2s;
    }

    .toggle input:checked + .toggle-track { background: var(--accent); }

    .toggle-thumb {
      position: absolute;
      top: 3px; left: 3px;
      width: 12px; height: 12px;
      background: #fff;
      border-radius: 50%;
      transition: left .2s;
    }

    .toggle input:checked ~ .toggle-thumb { left: 17px; }

    .hist-clear {
      background: none;
      border: 1px solid var(--border);
      border-radius: 5px;
      color: var(--muted);
      font-size: 11px;
      font-family: inherit;
      padding: 3px 8px;
      cursor: pointer;
      margin-top: 0;
      width: auto;
      transition: color .15s, border-color .15s;
    }

    .hist-clear:hover { color: var(--text); border-color: var(--muted); }

    .hist-del {
      background: none;
      border: none;
      color: var(--muted);
      font-size: 18px;
      line-height: 1;
      cursor: pointer;
      padding: 4px 7px;
      margin: 0;
      width: auto;
      margin-top: 0;
      border-radius: 5px;
      flex-shrink: 0;
      transition: color .15s, background .15s;
    }

    .hist-del:hover { color: var(--text); background: var(--surface2); }

    .hist-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 9px 10px;
      border-radius: 7px;
      cursor: pointer;
      transition: background .12s;
      gap: 12px;
    }

    .hist-item:hover { background: var(--surface2); }

    .hist-nome {
      font-size: 13.5px;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      flex: 1;
    }

    .hist-cpf {
      font-size: 12px;
      color: var(--muted);
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }

    .hist-time {
      font-size: 11px;
      color: var(--muted);
      white-space: nowrap;
    }

    .err-box {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 14px 18px;
      font-size: 14px;
      line-height: 1.5;
      color: var(--muted);
      margin-top: 14px;
    }

    .spin {
      width: 15px; height: 15px;
      border: 2px solid rgba(255,255,255,.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: rot .65s linear infinite;
      flex-shrink: 0;
    }

    /* ── multi-result header bar ── */
    .results-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-top: 14px;
      margin-bottom: 8px;
    }

    /* ── compact cards (> 3 results) ── */
    .cc-wrap { display: flex; flex-direction: column; gap: 6px; }

    .cc {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--r);
      padding: 11px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .cc--mismatch { border-color: #f0883e; border-left: 3px solid #f0883e; background: rgba(240,136,62,.04); }

    .cc-info { flex: 1; min-width: 0; }

    .cc-name {
      font-size: 14px;
      font-weight: 600;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .cc-sub {
      font-size: 12px;
      color: var(--muted);
      margin-top: 3px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      font-variant-numeric: tabular-nums;
    }

    .cc-badge { font-size: 12px; font-weight: 500; white-space: nowrap; flex-shrink: 0; }

    .btn-csv {
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--muted);
      font-size: 12px;
      font-family: inherit;
      padding: 4px 10px;
      cursor: pointer;
      margin-top: 0;
      width: auto;
      transition: color .15s, border-color .15s;
    }

    .btn-csv:hover { color: var(--text); border-color: var(--muted); }
  </style>
</head>
<body>

  <!-- gate: shown only when AUTH_REQUIRED and no token stored -->
  <div id="gate" style="display:none;width:100%;max-width:400px;text-align:center">
    <div class="logo">🔒</div>
    <h1>Acesso restrito</h1>
    <p class="sub">Informe o API Token para continuar</p>
    <div class="card" style="margin-top:20px">
      <div class="field">
        <label>API Token</label>
        <input id="gate-token" type="password" placeholder="Token de acesso" autocomplete="off" />
      </div>
      <button id="btn-gate" onclick="gateLogin()" style="margin-top:14px">Entrar</button>
      <div id="gate-msg" style="display:none;margin-top:10px;font-size:13px"></div>
    </div>
  </div>

  <!-- main: hidden until authenticated -->
  <div id="main-content">
  <div class="logo">🔍</div>
  <h1>CPF Validador</h1>
  <p class="sub">Verifique se um CPF é válido e a quem pertence</p>

  <div class="wrap">
    <div class="tabs">
      <div class="tab active" id="tab-consultar" onclick="switchTab('consultar')">Consultar</div>
      <div class="tab"        id="tab-historico" onclick="switchTab('historico')">Histórico</div>
    </div>

    <!-- aba consultar -->
    <div class="tab-panel active" id="panel-consultar">
      <div class="card">
        <div class="field">
          <label>CPF</label>
          <input id="cpf" type="text" placeholder="000.000.000-00"
                 spellcheck="false" autocomplete="off" inputmode="tel" />
          <p class="hint">Dígito ilegível? Use <code>*</code>, <code>X</code>, <code>?</code>, <code>_</code> ou <code>#</code> — ex: <code>***.879.820-**</code></p>
        </div>
        <div class="field">
          <label>Nome <span style="font-weight:400;text-transform:none;letter-spacing:0">(opcional)</span></label>
          <input id="nome" type="text" placeholder="Nome completo da pessoa" autocomplete="off" />
          <p class="hint">Confirma se o CPF pertence a esta pessoa</p>
        </div>
        <button id="btn" onclick="verificar()">Verificar</button>
      </div>

      <div id="log-box" class="log-box" style="display:none">
        <div class="log-head">
          <span>Progresso</span>
          <span class="elapsed" id="elapsed">0.0s</span>
        </div>
        <div id="steps"></div>
      </div>

      <div id="out"></div>
    </div>

    <!-- aba histórico -->
    <div class="tab-panel" id="panel-historico">
      <div class="card">
        <div class="hist-actions">
          <label class="toggle-wrap" title="Salvar automaticamente as consultas no histórico">
            <span class="toggle">
              <input type="checkbox" id="toggle-hist" onchange="setHistoryEnabled(this.checked)">
              <span class="toggle-track"></span>
              <span class="toggle-thumb"></span>
            </span>
            Salvar histórico
          </label>
          <div style="display:flex;gap:6px">
            <button class="hist-clear" onclick="downloadHistCSV()">↓ CSV</button>
            <button class="hist-clear" onclick="clearHistory()">Limpar</button>
          </div>
        </div>
        <div id="hist-list"></div>
      </div>
    </div>
  </div>
  </div><!-- /main-content -->

  <footer style="text-align:center;padding:20px 0 16px;font-size:12px;color:var(--muted);">
    <a href="https://github.com/opastorello/cpf-validador" target="_blank" rel="noopener"
       style="color:var(--muted);text-decoration:none;display:inline-flex;align-items:center;gap:6px;">
      <svg height="16" width="16" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38
        0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13
        -.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66
        .07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15
        -.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27
        .68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12
        .51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48
        0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
      </svg>
      opastorello/cpf-validador
    </a>
    <div style="margin-top:8px;">Consultando: <span id="fonte-ativa">__FONTE_ROTULO__</span></div>
  </footer>

  <script>
    const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    const safeUrl = u => (u && /^https?:\/\//i.test(u)) ? u : '#';

    const $cpf    = document.getElementById('cpf');
    const $nome   = document.getElementById('nome');
    const $btn    = document.getElementById('btn');
    const $out    = document.getElementById('out');
    const $logBox = document.getElementById('log-box');
    const $steps  = document.getElementById('steps');
    const $el     = document.getElementById('elapsed');

    /* ── CPF mask ── */
    $cpf.addEventListener('input', function() {
      const prev = this.value, pos = this.selectionStart;
      let raw = prev.replace(/[xX?_#]/g,'*').replace(/[^\d*]/g,'').slice(0,11);
      let fmt = raw;
      if (raw.length > 9)      fmt = raw.slice(0,3)+'.'+raw.slice(3,6)+'.'+raw.slice(6,9)+'-'+raw.slice(9);
      else if (raw.length > 6) fmt = raw.slice(0,3)+'.'+raw.slice(3,6)+'.'+raw.slice(6);
      else if (raw.length > 3) fmt = raw.slice(0,3)+'.'+raw.slice(3);
      this.value = fmt;
      const d = fmt.length - prev.length;
      this.setSelectionRange(pos+d, pos+d);
    });

    [$cpf, $nome].forEach(el => el.addEventListener('keydown', e => { if(e.key==='Enter') verificar(); }));

    /* ── timer ── */
    let _t = null;
    function startTimer() {
      const t0 = Date.now();
      $el.textContent = '0.0s';
      _t = setInterval(() => { $el.textContent = ((Date.now()-t0)/1000).toFixed(1)+'s'; }, 100);
    }
    function stopTimer() { clearInterval(_t); }

    /* ── steps ── */
    function resetLog() { $steps.innerHTML=''; $logBox.style.display='none'; $el.textContent='0.0s'; }

    function addStep(txt) {
      $logBox.style.display = 'block';
      const el = document.createElement('div');
      el.className = 'step pending';
      el.innerHTML = `<span class="si"></span><span>${txt}</span>`;
      $steps.appendChild(el);
      requestAnimationFrame(() => el.classList.add('show'));
      return el;
    }

    function doneStep(el, txt) { el.className='step show done'; if(txt) el.querySelector('span:last-child').textContent=txt; }
    function failStep(el, txt) { el.className='step show fail'; if(txt) el.querySelector('span:last-child').textContent=txt; }

    const delay = ms => new Promise(r => setTimeout(r, ms));
    const AUTH_REQUIRED = __AUTH_REQUIRED__;
    const USA_CAPTCHA   = __USA_CAPTCHA__;
    const FONTE_NOME    = "__FONTE_NOME__";
    const FONTE_ROTULO  = "__FONTE_ROTULO__";

    // Uma fonte sem CAPTCHA não pode anunciar que resolveu um. Os rótulos dos
    // passos seguem a capacidade declarada pela fonte ativa.
    const txtResolvendo = USA_CAPTCHA ? 'Resolvendo CAPTCHA…' : 'Consultando a fonte…';
    const txtResolvido  = USA_CAPTCHA ? 'CAPTCHA resolvido'   : 'Consulta concluída';
    const txtResolvidos = n => USA_CAPTCHA
      ? `${n} CAPTCHA${n!=1?'s':''} resolvido${n!=1?'s':''}`
      : `${n} consulta${n!=1?'s':''} concluída${n!=1?'s':''}`;
    const getToken = () => localStorage.getItem('api_token') || '';
    const authH = () => { const t = getToken(); return t ? {'Authorization': 'Bearer ' + t} : {}; };

    let _abort = null;
    let _lastResultados = [];
    let _lastBusca = '';

    function cancelar() { if (_abort) _abort.abort(); }

    function downloadCSV(dados) {
      const src = dados || _lastResultados;
      if (!src.length) return;
      const hdr = ['Nome','CPF','Tipo Certidão','Válida até','Nº Certidão'];
      const rows = src.map(d => [d.nome_certidao||'',d.cpf||'',d.tipo_certidao||'',d.valida_ate||'',d.numero_certidao||'']);
      const csv = [hdr,...rows].map(r=>r.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
      const slug = _lastBusca.replace(/[^a-zA-Z0-9.\-]/g, '_').replace(/_+/g,'_').replace(/^_|_$/g,'');
      const filename = `${slug}-${new Date().toISOString().slice(0,10)}.csv`;
      const a = Object.assign(document.createElement('a'),{
        href: URL.createObjectURL(new Blob(['﻿'+csv],{type:'text/csv;charset=utf-8'})),
        download: filename
      });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }

    /* ── main ── */
    async function verificar() {
      const cpf  = $cpf.value.trim();
      const nome = $nome.value.trim() || null;
      if (!cpf) { $cpf.focus(); return; }

      _abort = new AbortController();
      const {signal} = _abort;
      const post = (path, body) => fetch(path, {method:'POST', signal, headers:{'Content-Type':'application/json',...authH()}, body:JSON.stringify(body)});

      _lastBusca = cpf;
      $btn.onclick = cancelar;
      $btn.textContent = '✕ Cancelar';
      $btn.style.cssText = 'background:transparent;border:1px solid var(--border);color:var(--muted)';
      $out.innerHTML = '';
      resetLog();
      startTimer();

      const rawCpf   = cpf.replace(/[^\d*]/g,'');
      const hasMask  = rawCpf.includes('*');
      // só os curingas da base (posições 0-8) geram combinações — os dígitos
      // verificadores são recalculados pelo servidor, não enumerados
      const xs       = (rawCpf.slice(0,9).match(/\*/g)||[]).length;
      const unknowns = (rawCpf.match(/\*/g)||[]).length;

      let liveMatches = [];
      let resultados  = [];
      let inexistente = false;   // CPF válido no cálculo que a fonte não reconhece
      let msgInexistente = '';   // o texto vem da fonte: cada uma tem o seu
      let inexistentes = 0;      // quantos assim numa busca em lote
      let consultados = 0;       // quantos candidatos chegaram a ser consultados
      let interrompido = false;  // parou cedo por ter confirmado o nome

      // Candidatos que o TRT3 respondeu "não existe na Receita Federal": numa
      // busca por máscara costumam ser a maioria, e dizer isso explica por que
      // tantos candidatos não deram em nada.
      function contaInexistentes(payload) {
        const r = payload && payload.resultados;
        if (!r) return 0;
        return Object.values(r).filter(x => x && x.cpf_inexistente).length;
      }

      function renderLive() {
        if (!liveMatches.length) return;
        let sorted = [...liveMatches];
        if (nome) {
          const n = nome.toLowerCase();
          const sc = nm => {
            const s = nm.toLowerCase();
            if (s.startsWith(n)) return 0;
            if (s.split(/\s+/).some(w => w.startsWith(n))) return 1;
            return 2;
          };
          sorted.sort((a, b) => {
            const sa = sc(a.nome_certidao || ''), sb = sc(b.nome_certidao || '');
            return sa !== sb ? sa - sb : (a.nome_certidao || '').localeCompare(b.nome_certidao || '');
          });
        }
        $out.innerHTML = sorted.map(d => {
          const nomeReal = d.nome_certidao || '—';
          const cpfFmt   = d.cpf || cpf;
          const bate     = nome ? nomeMatch(nomeReal, nome) : null;
          const indicator = bate === true
            ? `<span class="result-indicator" style="color:#3fb950;font-weight:500;font-size:13px">✓ Confirmado</span>`
            : bate === false
            ? `<span class="result-indicator" style="color:#f0883e;font-weight:600;font-size:13px">✕ Nome não bate</span>`
            : '';
          const pdfLink = d.pdf_url
            ? `<a href="${safeUrl(d.pdf_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:none;font-weight:500">↗ Abrir PDF</a>`
            : '—';
          const cardClass = bate === false ? 'result-card result-card--mismatch' : 'result-card';
          return `<div class="${cardClass}">
            <div class="result-head"><span class="result-name">${esc(nomeReal)}</span>${indicator}</div>
            <div class="result-body">
              ${row('CPF', esc(cpfFmt))}
              ${d.numero_certidao ? row('Nº da certidão', esc(d.numero_certidao)) : ''}
              ${d.pdf_url ? row('Certidão PDF', pdfLink) : ''}
              ${bate === false ? row('⚠️ Nome buscado', `<span style="color:#f0883e;font-weight:500">${esc(nome)}</span>`) : ''}
            </div></div>`;
        }).join('');
      }

      try {
        /* 1 — validar */
        const s1 = addStep('Validando CPF…');
        await delay(250);

        let useVariations = false;

        if (!hasMask) {
          const vd = await (await post('/cpf/validate', {cpf})).json();
          if (!vd.valido) {
            useVariations = true;
            doneStep(s1, 'CPF inválido — buscando correções automaticamente…');
          } else {
            doneStep(s1, `CPF válido — ${vd.cpf_formatado}`);
          }
        } else {
          doneStep(s1, `Máscara: ${unknowns} dígito${unknowns>1?'s':''} desconhecido${unknowns>1?'s':''}`);
        }

        /* 2 — candidatos */
        let totalCandidatos = 1;
        const estimadoCandidatos = hasMask ? Math.pow(10, xs) : 1;
        const s2 = addStep(useVariations
          ? 'Calculando variações válidas…'
          : hasMask
          ? `Calculando combinações para ${xs} dígito${xs>1?'s':''} desconhecido${xs>1?'s':''}…`
          : 'Preparando consulta…');
        await delay(300);
        let variations = [];
        if (useVariations) {
          const vrResp = await post('/cpf/variations', {cpf});
          const vrData = await vrResp.json();
          variations = vrData.variations || [];
          totalCandidatos = variations.length;
          if (!totalCandidatos) throw new Error('Nenhuma variação válida encontrada para este CPF');
          doneStep(s2, `${totalCandidatos} variaç${totalCandidatos!==1?'ões':'ão'} válida${totalCandidatos!==1?'s':''}`);
        } else {
          doneStep(s2, hasMask ? 'Calculando…' : '1 CPF');
        }

        /* 3 — conectar */
        const s3 = addStep('Conectando ao servidor…');
        await delay(300);
        doneStep(s3, 'Conexão estabelecida');

        /* 4 — captcha (fetch real) */
        const s4 = addStep(useVariations
          ? 'Testando variações…'
          : hasMask
          ? 'Aguardando contagem de candidatos…'
          : txtResolvendo);

        if (useVariations) {
          s4.querySelector('span:last-child').textContent = `Expandindo — 0/${totalCandidatos} variações…`;
          const vresp = await fetch('/consulta/buscar-por-variacoes/stream', {
            method: 'POST', signal,
            headers: {'Content-Type': 'application/json', ...authH()},
            body: JSON.stringify({cpf_parcial: cpf, nome, workers: 8}),
          });
          if (!vresp.ok) {
            let msg = `Erro HTTP ${vresp.status}`;
            try { const e = await vresp.json(); msg = e.detail || e.error || msg; } catch {}
            const err = new Error(msg);
            if (vresp.status === 429) err._retryAfter = parseInt(vresp.headers.get('Retry-After') || '60');
            throw err;
          }
          const vreader = vresp.body.getReader();
          const vdec = new TextDecoder();
          let vbuf = '', vfinal = null;
          vouter: while (true) {
            const {done, value} = await vreader.read();
            if (done) break;
            vbuf += vdec.decode(value, {stream: true});
            let boundary;
            while ((boundary = vbuf.indexOf('\n\n')) !== -1) {
              const chunk = vbuf.slice(0, boundary);
              vbuf = vbuf.slice(boundary + 2);
              if (!chunk.startsWith('data: ')) continue;
              const evt = JSON.parse(chunk.slice(6));
              if (evt.progress !== undefined) {
                s4.querySelector('span:last-child').textContent = `${evt.progress}/${evt.total} variações testadas…`;
              } else if (evt.match) {
                liveMatches.push(evt.match); renderLive();
              } else if (evt.done) {
                vfinal = evt.result;
                break vouter;
              } else if (evt.error) { throw new Error(evt.error); }
            }
          }
          if (!vfinal) throw new Error('Stream de variações encerrado sem resultado');
          doneStep(s4, txtResolvidos(vfinal.consultados ?? totalCandidatos));
          inexistentes = contaInexistentes(vfinal);
          consultados  = vfinal.consultados ?? totalCandidatos;
          interrompido = !!vfinal.interrompido;
          resultados = liveMatches;
        } else if (hasMask) {
          const mascara = rawCpf;
          const resp = await fetch('/consulta/buscar-por-mascara/stream', {
            method: 'POST',
            signal,
            headers: {'Content-Type': 'application/json', ...authH()},
            body: JSON.stringify({mascara, nome, workers: 8}),
          });
          if (!resp.ok) {
            let msg = `Erro HTTP ${resp.status}`;
            try { const e = await resp.json(); msg = e.detail || e.error || msg; } catch {}
            const err = new Error(msg);
            if (resp.status === 429) err._retryAfter = parseInt(resp.headers.get('Retry-After') || '60');
            throw err;
          }

          const reader = resp.body.getReader();
          const dec = new TextDecoder();
          let buf = '';
          let finalData = null;

          outer: while (true) {
            const {done, value} = await reader.read();
            if (done) break;
            buf += dec.decode(value, {stream: true});
            let boundary;
            while ((boundary = buf.indexOf('\n\n')) !== -1) {
              const chunk = buf.slice(0, boundary);
              buf = buf.slice(boundary + 2);
              if (!chunk.startsWith('data: ')) continue;
              const evt = JSON.parse(chunk.slice(6));
              if (evt.total && evt.progress === undefined && !evt.done && !evt.match) {
                s2.querySelector('span:last-child').textContent =
                  `${evt.total} combinaç${evt.total!=1?'ões':'ão'} calculada${evt.total!=1?'s':''}`;
                s4.querySelector('span:last-child').textContent = evt.total === 1
                  ? txtResolvendo
                  : `Testando em paralelo… 0/${evt.total}`;
              } else if (evt.progress !== undefined) {
                s4.querySelector('span:last-child').textContent = evt.total === 1
                  ? txtResolvendo
                  : `Testando em paralelo… ${evt.progress}/${evt.total}`;
              } else if (evt.match) {
                liveMatches.push(evt.match); renderLive();
              } else if (evt.done) {
                finalData = evt.result;
                break outer;
              } else if (evt.error) {
                throw new Error(evt.error);
              }
            }
          }

          if (!finalData) throw new Error('Stream encerrado sem resultado');
          totalCandidatos = finalData.candidatos_gerados || '?';
          s2.querySelector('span:last-child').textContent = `${totalCandidatos} combinaç${totalCandidatos!=1?'ões':'ão'} calculada${totalCandidatos!=1?'s':''}`;
          doneStep(s4, txtResolvidos(finalData.consultados ?? totalCandidatos));
          inexistentes = contaInexistentes(finalData);
          consultados  = finalData.consultados ?? totalCandidatos;
          interrompido = !!finalData.interrompido;
          resultados = liveMatches;
        } else {
          const res  = await post('/consulta/cpf', {cpf});
          const data = await res.json();
          if (!res.ok) throw new Error(data.detail || 'Erro na consulta');
          doneStep(s4, txtResolvido);
          inexistente = !!data.cpf_inexistente;
          msgInexistente = data.mensagem || '';
          if (data.nome_certidao) resultados = [data];
        }

        stopTimer();

        if (!resultados.length) {
          if (inexistente) {
            // Caso distinto de "não tem processos": a fonte não reconhece o CPF.
            // O texto vem da fonte — "Receita Federal" é vocabulário do TRT3 e
            // não valeria para outra fonte.
            const msg = msgInexistente || 'CPF não localizado na base consultada.';
            $out.innerHTML = `<div class="err-box">⚠️ ${esc(msg)}</div>`;
            return;
          }
          const semRegistro = inexistentes
            ? `, ${esc(String(inexistentes))} deles não reconhecidos pela fonte`
            : '';
          $out.innerHTML = `<div class="err-box">⚠️ Nenhum resultado encontrado${nome ? ` para "${esc(nome)}"` : ''}${(hasMask || useVariations) ? ` — ${esc(String(totalCandidatos))} candidatos testados${semRegistro}` : ''}.</div>`;
          return;
        }

        if (nome) {
          const n = nome.toLowerCase();
          const score = nm => {
            const s = nm.toLowerCase();
            if (s.startsWith(n)) return 0;
            if (s.split(/\s+/).some(w => w.startsWith(n))) return 1;
            return 2;
          };
          resultados.sort((a, b) => {
            const sa = score(a.nome_certidao || '');
            const sb = score(b.nome_certidao || '');
            if (sa !== sb) return sa - sb;
            return (a.nome_certidao || '').localeCompare(b.nome_certidao || '');
          });
        }

        const duracaoS = parseFloat($el.textContent);
        _lastResultados = resultados;
        resultados.forEach(d => {
          if (d.nome_certidao) saveToHistory(d.cpf || cpf, d.nome_certidao, d.numero_certidao || null, duracaoS || null);
        });

        // Mostra o resumo também com um único resultado quando a busca parou
        // cedo: é justamente aí que interessa dizer quantos foram testados.
        const metaStr = (hasMask || useVariations) && (resultados.length > 1 || interrompido)
          ? `${resultados.length} resultado${resultados.length!==1?'s':''} · ${interrompido ? `${consultados} de ${totalCandidatos} testados — nome confirmado` : `${totalCandidatos} candidatos`}${inexistentes ? ` · ${inexistentes} inexistentes` : ''} · ${$el.textContent}`
          : resultados.length > 1 ? `${resultados.length} resultados` : '';

        const mkCard = d => {
          const nomeReal = d.nome_certidao || '—';
          const cpfFmt   = d.cpf || cpf;
          const bate     = nome ? nomeMatch(nomeReal, nome) : null;
          const indicator = bate === true
            ? `<span class="result-indicator" style="color:#3fb950;font-weight:500;font-size:13px">✓ Confirmado</span>`
            : bate === false
            ? `<span class="result-indicator" style="color:#f0883e;font-weight:600;font-size:13px">✕ Nome não bate</span>`
            : '';
          const pdfLink = d.pdf_url
            ? `<a href="${safeUrl(d.pdf_url)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:none;font-weight:500">↗ Abrir PDF</a>`
            : '—';
          const cardClass = bate === false ? 'result-card result-card--mismatch' : 'result-card';
          return `<div class="${cardClass}">
            <div class="result-head"><span class="result-name">${esc(nomeReal)}</span>${indicator}</div>
            <div class="result-body">
              ${row('CPF', esc(cpfFmt))}
              ${d.numero_certidao ? row('Nº da certidão', esc(d.numero_certidao)) : ''}
              ${d.pdf_url ? row('Certidão PDF', pdfLink) : ''}
              ${bate === false ? row('⚠️ Nome buscado', `<span style="color:#f0883e;font-weight:500">${esc(nome)}</span>`) : ''}
            </div></div>`;
        };

        const cardsHtml = resultados.map(mkCard).join('');
        if (metaStr) {
          $out.innerHTML = `<div class="results-bar"><span class="meta" style="margin:0">${metaStr}</span><button class="btn-csv" onclick="downloadCSV()">↓ CSV</button></div>${cardsHtml}`;
        } else {
          $out.innerHTML = cardsHtml;
        }

      } catch(e) {
        stopTimer();
        $steps.querySelectorAll('.step:not(.done):not(.fail)').forEach(el => failStep(el, null));
        if (e.name === 'AbortError') {
          $out.innerHTML = `<div class="err-box">Busca cancelada.</div>`;
        } else if (e._retryAfter) {
          let rem = e._retryAfter;
          const tick = () => {
            $out.innerHTML = `<div class="err-box">⚠️ Rate limit — nova busca em ${rem}s.</div>`;
            if (--rem >= 0) setTimeout(tick, 1000);
          };
          tick();
        } else {
          $out.innerHTML = `<div class="err-box">⚠️ ${esc(e.message)}</div>`;
        }
      } finally {
        $btn.onclick = verificar;
        $btn.textContent = 'Verificar';
        $btn.style.cssText = '';
        $btn.disabled = false;
      }
    }

    /* ── gate ── */
    function updateTabLock() {
      const locked = AUTH_REQUIRED && !getToken();
      document.getElementById('gate').style.display         = locked ? 'block' : 'none';
      document.getElementById('main-content').style.display = locked ? 'none' : '';
    }

    async function gateLogin() {
      const tok = document.getElementById('gate-token').value.trim();
      if (!tok) return;
      const btn = document.getElementById('btn-gate');
      const msg = document.getElementById('gate-msg');
      btn.disabled = true;
      btn.textContent = 'Validando…';
      try {
        const res = await fetch('/auth/check', { headers: { 'Authorization': 'Bearer ' + tok } });
        if (res.status === 401) {
          showGateMsg('✕ Token inválido.', 'var(--err-text)');
          btn.disabled = false; btn.textContent = 'Entrar';
          return;
        }
        if (!res.ok) {
          showGateMsg('⚠ Erro ao validar (HTTP ' + res.status + ').', 'var(--err-text)');
          btn.disabled = false; btn.textContent = 'Entrar';
          return;
        }
      } catch {
        showGateMsg('⚠ Erro ao validar.', 'var(--err-text)');
        btn.disabled = false; btn.textContent = 'Entrar';
        return;
      }
      localStorage.setItem('api_token', tok);
      btn.disabled = false; btn.textContent = 'Entrar';
      updateTabLock();
    }

    function showGateMsg(text, color) {
      const msg = document.getElementById('gate-msg');
      msg.textContent = text; msg.style.color = color; msg.style.display = 'block';
      setTimeout(() => { msg.style.display = 'none'; }, 3000);
    }

    /* init */
    document.getElementById('gate-token').addEventListener('keydown', e => { if (e.key === 'Enter') gateLogin(); });
    updateTabLock();

    /* ── tabs ── */
    function switchTabRaw(name) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      document.getElementById('tab-' + name).classList.add('active');
      document.getElementById('panel-' + name).classList.add('active');
      if (name === 'historico') { initHistoryToggle(); renderHistory(); }
    }

    function switchTab(name) {
      if (AUTH_REQUIRED && !getToken()) return;
      switchTabRaw(name);
    }

    /* ── history (localStorage — por browser/usuário) ── */
    const $histList = document.getElementById('hist-list');
    const HIST_KEY = 'cpf_validador_history';

    const isHistoryEnabled = () => localStorage.getItem('history_enabled') !== 'false';
    function setHistoryEnabled(val) { localStorage.setItem('history_enabled', val ? 'true' : 'false'); }
    function initHistoryToggle() { document.getElementById('toggle-hist').checked = isHistoryEnabled(); }

    function histLoad() { try { return JSON.parse(localStorage.getItem(HIST_KEY) || '{}'); } catch { return {}; } }
    function histSave(d) { localStorage.setItem(HIST_KEY, JSON.stringify(d)); }

    // A chave inclui a fonte: o número de certidão é de quem emitiu, então o
    // mesmo CPF consultado no TRT3 e no TCU são duas entradas, não uma que
    // sobrescreve a outra.
    function saveToHistory(cpf, nome, numero_certidao, duracao_segundos) {
      if (!isHistoryEnabled()) return;
      const data = histLoad();
      const key  = cpf + '::' + FONTE_NOME;
      const now  = new Date().toISOString();
      if (data[key]) {
        data[key].consultas++;
        data[key].ultima_consulta = now;
        if (nome) data[key].nome = nome;
        if (numero_certidao) data[key].numero_certidao = numero_certidao;
        if (duracao_segundos != null) data[key].ultima_duracao_s = Math.round(duracao_segundos * 10) / 10;
      } else {
        data[key] = { cpf, fonte: FONTE_NOME, fonte_rotulo: FONTE_ROTULO,
          nome, numero_certidao, consultas: 1,
          primeira_consulta: now, ultima_consulta: now,
          ultima_duracao_s: duracao_segundos != null ? Math.round(duracao_segundos * 10) / 10 : null };
      }
      histSave(data);
    }

    function clearHistory() { localStorage.removeItem(HIST_KEY); renderHistory(); }

    function downloadHistCSV() {
      const data = histLoad();
      const entries = Object.values(data);
      if (!entries.length) return;
      const hdr = ['Nome','CPF','Fonte','Nº Certidão','Consultas','Última consulta','Duração (s)'];
      const rows = entries.map(h => [h.nome||'',h.cpf||'',h.fonte_rotulo||h.fonte||'',h.numero_certidao||'',h.consultas||'',h.ultima_consulta||'',h.ultima_duracao_s||'']);
      const csv = [hdr,...rows].map(r=>r.map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
      const a = Object.assign(document.createElement('a'),{
        href: URL.createObjectURL(new Blob(['﻿'+csv],{type:'text/csv;charset=utf-8'})),
        download: `historico-${new Date().toISOString().slice(0,10)}.csv`
      });
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }

    function deleteHistoryEntry(chave) {
      const data = histLoad();
      delete data[chave];
      histSave(data);
      renderHistory();
    }

    function fmtDt(iso) {
      if (!iso) return '—';
      const d = new Date(iso);
      const today = new Date();
      const hm = d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
      if (d.toDateString() === today.toDateString()) return 'Hoje ' + hm;
      return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: '2-digit' }) + ' ' + hm;
    }

    function renderHistory() {
      const data = histLoad();
      const entries = Object.entries(data).sort(([, a], [, b]) =>
        (b.ultima_consulta || '') > (a.ultima_consulta || '') ? 1 : -1);
      if (!entries.length) {
        $histList.innerHTML = '<div class="hist-empty">Nenhuma consulta registrada ainda.</div>';
        return;
      }
      $histList.innerHTML = entries.map(([key, h]) => `
        <div class="hist-item" onclick="fillFromHistory('${esc(h.cpf)}','${esc(h.nome||'')}')">
          <div style="flex:1;min-width:0">
            <div class="hist-nome">${esc(h.nome) || '—'}</div>
            <div style="font-size:12px;color:var(--muted);margin-top:2px;display:flex;gap:10px;flex-wrap:wrap">
              <span>${esc(h.cpf)}</span>
              ${h.fonte ? `<span>${esc(h.fonte_rotulo || h.fonte)}</span>` : ''}
              ${h.numero_certidao ? `<span>Certidão ${esc(h.numero_certidao)}</span>` : ''}
              ${h.ultima_duracao_s != null ? `<span>${esc(h.ultima_duracao_s)}s</span>` : ''}
            </div>
          </div>
          <div style="text-align:right;flex-shrink:0">
            <div class="hist-time">${fmtDt(h.ultima_consulta)}</div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px">${esc(h.consultas)}× consultado</div>
          </div>
          <button class="hist-del" title="Remover entrada"
            onclick="event.stopPropagation(); deleteHistoryEntry('${esc(key)}')">×</button>
        </div>`).join('');
    }

    function fillFromHistory(cpf, nome) {
      switchTab('consultar');
      $cpf.value = cpf;
      $nome.value = nome || '';
      $out.innerHTML = '';
      $logBox.style.display = 'none';
      $steps.innerHTML = '';
    }

    function nomeMatch(a, b) {
      const n = s => s.toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g,'').trim();
      const na = n(a), nb = n(b);
      return na === nb || nb.split(/\s+/).every(w => new RegExp('(?:^|\\s)' + w + '(?:\\s|$)').test(na));
    }

    function row(l, v) {
      return `<div class="row"><span class="row-l">${l}</span><span class="row-v">${v}</span></div>`;
    }
  </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
async def ui():
    auth_required = "true" if _TOKEN else "false"
    # A fonte ativa é importada aqui na primeira carga da página; seria
    # importada de todo jeito na primeira consulta.
    fonte = get_fonte()
    usa_captcha = "true" if fonte.usa_captcha else "false"
    return (_HTML.replace("__AUTH_REQUIRED__", auth_required)
                 .replace("__USA_CAPTCHA__", usa_captcha)
                 .replace("__FONTE_ROTULO__", escape(fonte.rotulo))
                 .replace("__FONTE_NOME__", escape(fonte.nome)))

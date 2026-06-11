// ============================================================
// AgentOS — Main Application
// ============================================================

// ── Particle System ──────────────────────────────────────────
class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.shootingStars = [];
        this.resize();
        window.addEventListener('resize', () => this.resize());
        this._init();
    }

    resize() {
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.canvas.style.width = window.innerWidth + 'px';
        this.canvas.style.height = window.innerHeight + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.w = window.innerWidth;
        this.h = window.innerHeight;
    }

    _init() {
        for (let i = 0; i < 120; i++) {
            this.particles.push({
                x: Math.random() * this.w,
                y: Math.random() * this.h,
                size: Math.random() * 1.8 + 0.3,
                speedY: -(Math.random() * 0.15 + 0.03),
                speedX: (Math.random() - 0.5) * 0.05,
                opacity: Math.random() * 0.5 + 0.1,
                twinkleSpeed: Math.random() * 0.02 + 0.005,
                twinklePhase: Math.random() * Math.PI * 2,
                hue: Math.random() < 0.3 ? 220 + Math.random() * 40 : 270 + Math.random() * 30,
            });
        }
    }

    update() {
        this.ctx.clearRect(0, 0, this.w, this.h);

        for (const p of this.particles) {
            p.x += p.speedX;
            p.y += p.speedY;
            p.twinklePhase += p.twinkleSpeed;

            if (p.y < -5) { p.y = this.h + 5; p.x = Math.random() * this.w; }
            if (p.x < -5) p.x = this.w + 5;
            if (p.x > this.w + 5) p.x = -5;

            const twinkle = (Math.sin(p.twinklePhase) + 1) / 2;
            const alpha = p.opacity * (0.5 + twinkle * 0.5);

            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = `hsla(${p.hue}, 60%, 75%, ${alpha})`;
            this.ctx.fill();
        }

        if (Math.random() < 0.003) {
            this.shootingStars.push({
                x: Math.random() * this.w,
                y: Math.random() * this.h * 0.3,
                vx: 4 + Math.random() * 4,
                vy: 2 + Math.random() * 2,
                life: 1,
                length: 30 + Math.random() * 40,
            });
        }

        for (let i = this.shootingStars.length - 1; i >= 0; i--) {
            const s = this.shootingStars[i];
            s.x += s.vx;
            s.y += s.vy;
            s.life -= 0.02;

            if (s.life <= 0) { this.shootingStars.splice(i, 1); continue; }

            const gradient = this.ctx.createLinearGradient(
                s.x, s.y, s.x - s.vx * s.length / 5, s.y - s.vy * s.length / 5
            );
            gradient.addColorStop(0, `rgba(255, 255, 255, ${s.life * 0.8})`);
            gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

            this.ctx.beginPath();
            this.ctx.moveTo(s.x, s.y);
            this.ctx.lineTo(s.x - s.vx * s.length / 5, s.y - s.vy * s.length / 5);
            this.ctx.strokeStyle = gradient;
            this.ctx.lineWidth = 1.5;
            this.ctx.stroke();
        }
    }

    startLoop() {
        const loop = () => { this.update(); requestAnimationFrame(loop); };
        requestAnimationFrame(loop);
    }
}

// ── Feed Manager ─────────────────────────────────────────────
class FeedManager {
    constructor() {
        this.container = document.getElementById('feed-container');
        this.items = document.getElementById('feed-items');
        this.badge = document.getElementById('feed-badge');
        this.expanded = false;
        this.unread = 0;

        document.getElementById('feed-handle').addEventListener('click', () => this.toggle());
        document.getElementById('feed-header').addEventListener('click', () => this.toggle());
    }

    toggle() {
        this.expanded = !this.expanded;
        this.container.classList.toggle('expanded', this.expanded);
        if (this.expanded) { this.unread = 0; this.badge.classList.add('hidden'); }
    }

    addItem(data) {
        const item = document.createElement('div');
        item.className = 'feed-item';

        if (data.type === 'discovery') item.classList.add('discovery');
        if (data.type === 'user_alert') item.classList.add('alert');

        const color = data.metadata?.color || '#fff';
        item.style.setProperty('--item-color', color);

        const time = new Date((data.timestamp || Date.now() / 1000) * 1000);
        const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        const emoji = data.metadata?.emoji || '🤖';
        const sender = data.sender || 'System';
        let displayContent = data.content || '';

        if (data.type === 'agent_chat' && data.recipient && data.recipient !== 'all') {
            displayContent = `→ ${data.recipient}: ${displayContent}`;
        }

        // H1 fix: sanitize all user content to prevent XSS
        const esc = (s) => {
            const d = document.createElement('div');
            d.textContent = s;
            return d.innerHTML;
        };

        item.innerHTML = `
            <div class="feed-item-emoji">${esc(emoji)}</div>
            <div class="feed-item-body">
                <div class="feed-item-header">
                    <span class="feed-item-sender" style="color:${color}">${esc(sender)}</span>
                    <span class="feed-item-time">${timeStr}</span>
                </div>
                <div class="feed-item-content">${esc(displayContent)}</div>
            </div>
        `;

        this.items.insertBefore(item, this.items.firstChild);
        while (this.items.children.length > 100) this.items.removeChild(this.items.lastChild);

        if (!this.expanded) {
            this.unread++;
            this.badge.textContent = this.unread > 99 ? '99+' : this.unread;
            this.badge.classList.remove('hidden');
        }
    }
}

// ── Agent Detail Modal ───────────────────────────────────────
class DetailModal {
    constructor(renderer) {
        this.el = document.getElementById('agent-detail');
        this.renderer = renderer;
        this.findings = new Map();

        document.getElementById('detail-close').addEventListener('click', () => this.close());
        document.querySelector('.detail-backdrop').addEventListener('click', () => this.close());
    }

    open(agentName) {
        const agent = this.renderer.getAgentInfo(agentName);
        if (!agent) return;

        document.getElementById('detail-avatar').textContent = agent.emoji;
        document.getElementById('detail-avatar').style.setProperty('--agent-color', agent.color);
        document.getElementById('detail-avatar').style.setProperty('--agent-color-alpha', agent.color + '40');
        document.getElementById('detail-name').textContent = agent.name;
        document.getElementById('detail-app').textContent = agent.app || agent.app_name || '';
        document.getElementById('detail-status').textContent = agent.current_task || 'Idle';

        const findingsEl = document.getElementById('detail-findings');
        findingsEl.innerHTML = '';

        const agentFindings = this.findings.get(agentName) || [];
        for (const f of agentFindings.slice(-8)) {
            const div = document.createElement('div');
            div.className = 'detail-finding';
            div.style.setProperty('--agent-color', agent.color);
            div.textContent = f;
            findingsEl.appendChild(div);
        }

        if (agentFindings.length === 0) {
            findingsEl.innerHTML = '<div class="detail-finding" style="opacity:0.4">No findings yet — agent is warming up...</div>';
        }

        this.el.classList.remove('hidden');
    }

    close() { this.el.classList.add('hidden'); }

    addFinding(agentName, content) {
        if (!this.findings.has(agentName)) this.findings.set(agentName, []);
        const list = this.findings.get(agentName);
        list.push(content);
        if (list.length > 50) list.shift();
    }
}

// ── Context Reporter ─────────────────────────────────────────
class ContextReporter {
    constructor(ws) {
        this.ws = ws;
        this._watchVisibility();
        this._watchGeolocation();
    }

    _watchVisibility() {
        document.addEventListener('visibilitychange', () => {
            this.ws.send({
                type: 'context_update',
                data: { screen_on: !document.hidden },
            });
        });
    }

    _watchGeolocation() {
        if (!navigator.geolocation) return;

        // Request once on start, then every 5 minutes
        const getPos = () => {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    this.ws.send({
                        type: 'context_update',
                        data: {
                            lat: pos.coords.latitude,
                            lon: pos.coords.longitude,
                        },
                    });
                },
                () => {},
                { enableHighAccuracy: false, timeout: 10000 },
            );
        };

        // Don't request immediately — wait for user interaction
        setTimeout(getPos, 5000);
        setInterval(getPos, 300000);
    }
}

// ── Permission Dialog ────────────────────────────────────────
class PermissionUI {
    constructor(ws) {
        this.ws = ws;
    }

    show(data) {
        const meta = data.metadata || {};
        if (meta.type !== 'permission_request') return;

        const agent = meta.agent || 'Agent';
        const cap = meta.capability || 'unknown';
        const requestId = meta.request_id || '';

        // H9: XSS-safe permission dialog
        const esc = (s) => { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; };

        const overlay = document.createElement('div');
        overlay.className = 'permission-overlay';
        overlay.innerHTML = `
            <div class="permission-card">
                <div class="permission-icon">🔐</div>
                <h3>Permission Request</h3>
                <p><strong>${esc(agent)}</strong> wants to use <strong>${esc(cap)}</strong></p>
                <div class="permission-buttons">
                    <button class="perm-deny">Deny</button>
                    <button class="perm-allow">Allow</button>
                </div>
            </div>
        `;

        overlay.querySelector('.perm-allow').onclick = () => {
            this.ws.send({ type: 'permission_response', request_id: requestId, granted: true });
            overlay.remove();
        };
        overlay.querySelector('.perm-deny').onclick = () => {
            this.ws.send({ type: 'permission_response', request_id: requestId, granted: false });
            overlay.remove();
        };

        document.body.appendChild(overlay);
    }
}

// ── Command Bar (talk to your agents) ────────────────────────
class CommandBar {
    constructor(ws) {
        this.ws = ws;
        this.input = document.getElementById('command-input');
        this.toasts = document.getElementById('command-toasts');
        this.lastInputWasVoice = false;
        this.voice = new VoiceControl(this);

        document.getElementById('command-bar').addEventListener('submit', (e) => {
            e.preventDefault();
            this.submit(this.input.value, false);
        });
    }

    submit(text, viaVoice) {
        text = (text || '').trim();
        if (!text) return;
        this.lastInputWasVoice = viaVoice;
        this.ws.send({ type: 'user_command', text });
        this.showToast(`🗣 ${text}`, 'user');
        this.input.value = '';
    }

    // Render an assistant reply; pop a confirm dialog for high-risk actions
    handleReply(data) {
        const meta = data.metadata || {};
        this.showToast(data.content || '', 'assistant');
        if (this.lastInputWasVoice) {
            this.voice.speak(data.content || '');
        }
        if (meta.requires_confirmation && meta.pending_id) {
            this._confirmDialog(meta);
        }
    }

    showToast(text, kind) {
        const toast = document.createElement('div');
        toast.className = `command-toast ${kind}`;
        toast.textContent = text;
        this.toasts.appendChild(toast);
        while (this.toasts.children.length > 4) {
            this.toasts.removeChild(this.toasts.firstChild);
        }
        setTimeout(() => {
            toast.classList.add('fading');
            setTimeout(() => toast.remove(), 400);
        }, 7000);
    }

    _confirmDialog(meta) {
        const esc = (s) => { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; };
        const params = meta.params ? JSON.stringify(meta.params) : '';

        const overlay = document.createElement('div');
        overlay.className = 'permission-overlay';
        overlay.innerHTML = `
            <div class="permission-card">
                <div class="permission-icon">🔐</div>
                <h3>Confirm Action</h3>
                <p><strong>${esc(meta.action_id || 'action')}</strong></p>
                <p class="confirm-params">${esc(params)}</p>
                <div class="permission-buttons">
                    <button class="perm-deny">Cancel</button>
                    <button class="perm-allow">Confirm</button>
                </div>
            </div>
        `;

        overlay.querySelector('.perm-allow').onclick = () => {
            this.ws.send({ type: 'confirm_action', pending_id: meta.pending_id, approved: true });
            overlay.remove();
        };
        overlay.querySelector('.perm-deny').onclick = () => {
            this.ws.send({ type: 'confirm_action', pending_id: meta.pending_id, approved: false });
            overlay.remove();
        };

        document.body.appendChild(overlay);
    }
}

// ── Voice Control (speech in, speech out) ────────────────────
class VoiceControl {
    constructor(commandBar) {
        this.commandBar = commandBar;
        this.button = document.getElementById('command-mic');
        this.listening = false;
        this.recognition = null;

        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            this.button.style.display = 'none';
            return;
        }

        this.recognition = new SR();
        this.recognition.lang = navigator.language || 'en-US';
        this.recognition.interimResults = false;
        this.recognition.maxAlternatives = 1;

        this.recognition.onresult = (event) => {
            const text = event.results[0][0].transcript;
            this.commandBar.submit(text, true);
        };
        this.recognition.onend = () => this._setListening(false);
        this.recognition.onerror = () => this._setListening(false);

        this.button.addEventListener('click', () => this.toggle());
    }

    toggle() {
        if (!this.recognition) return;
        if (this.listening) {
            this.recognition.stop();
            return;
        }
        try {
            this.recognition.start();
            this._setListening(true);
        } catch (e) {
            this._setListening(false);
        }
    }

    _setListening(on) {
        this.listening = on;
        this.button.classList.toggle('listening', on);
    }

    speak(text) {
        if (!('speechSynthesis' in window) || !text) return;
        speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text.replace(/[—🔐⚡🛑🤖]/g, ''));
        utterance.rate = 1.05;
        speechSynthesis.speak(utterance);
    }
}

// ── Demo Mode ────────────────────────────────────────────────
class DemoMode {
    constructor(app) {
        this.app = app;
        this.running = false;
    }

    start() {
        if (this.running) return;
        this.running = true;
        this._loop();
    }

    stop() { this.running = false; }

    async _loop() {
        const types = ['agent_update', 'agent_chat', 'discovery', 'agent_update'];

        while (this.running) {
            const agents = this.app.agentsList;
            if (agents.length === 0) { await new Promise(r => setTimeout(r, 1000)); continue; }

            const agent = agents[Math.floor(Math.random() * agents.length)];
            const type = types[Math.floor(Math.random() * types.length)];

            const msg = {
                sender: agent.name,
                recipient: 'all',
                type: type,
                content: this._generateContent(type, agent),
                timestamp: Date.now() / 1000,
                metadata: { emoji: agent.emoji, color: agent.color, app: agent.app },
            };

            if (type === 'agent_chat') {
                const other = agents.filter(a => a.name !== agent.name);
                if (other.length > 0) msg.recipient = other[Math.floor(Math.random() * other.length)].name;
            }

            this.app.handleMessage(msg);
            await new Promise(r => setTimeout(r, 3000 + Math.random() * 5000));
        }
    }

    _generateContent(type, agent) {
        const updates = [
            'scanning for new content...', 'analyzing latest trends...',
            'cross-referencing findings...', 'compiling insights...',
            `monitoring ${agent.app || agent.name}...`,
        ];
        const chats = [
            'Found something interesting — check this out!',
            'This connects to what you mentioned earlier.',
            'The data on this is pretty compelling.',
            'Heads up — this is trending and relevant.',
            'Quick update from my end — all looking good.',
        ];
        const discoveries = [
            'New trend: AI agent frameworks seeing 5x adoption growth.',
            'Ethiopian tech startups raised $200M+ in early 2026.',
            'Pattern: User engagement peaks correlate with lo-fi music.',
            'Major open-source AI model matches proprietary benchmarks.',
            'Developer tool spending up 40% YoY — agents leading.',
        ];

        const pool = type === 'agent_update' ? updates : type === 'agent_chat' ? chats : discoveries;
        return pool[Math.floor(Math.random() * pool.length)];
    }
}

// ── Main App ─────────────────────────────────────────────────
class PhoneAgentsApp {
    constructor() {
        this.agentsList = [];
        this.particles = new ParticleSystem(document.getElementById('particle-canvas'));
        this.renderer = new AgentsRenderer(
            document.getElementById('agent-layer'),
            document.getElementById('connection-lines')
        );
        this.feed = new FeedManager();
        this.detail = new DetailModal(this.renderer);
        this.ws = new AgentWebSocket();
        this.demo = new DemoMode(this);
        this.permissionUI = new PermissionUI(this.ws);
        this.commandBar = new CommandBar(this.ws);
        this.contextReporter = null;

        this.renderer.onAgentTap = (name) => this.detail.open(name);

        this._loadAgents();
        this._setupWebSocket();
        this.particles.startLoop();
    }

    async _loadAgents() {
        try {
            const resp = await AgentAuth.fetch('/api/agents');
            if (resp.ok) {
                this.agentsList = await resp.json();
                this.renderer.initAgents(this.agentsList);
                document.getElementById('agent-count').textContent = `${this.agentsList.length} agents`;
                return;
            }
        } catch (e) {
            console.log('Could not fetch agents, using defaults');
        }

        // Fallback defaults
        this.agentsList = [
            { name: 'Claude', emoji: '🧠', color: '#D4A574', app: 'Claude', current_task: '' },
            { name: 'Spotify', emoji: '🎵', color: '#1DB954', app: 'Spotify', current_task: '' },
            { name: 'Reddit', emoji: '🔥', color: '#FF4500', app: 'Reddit', current_task: '' },
            { name: 'X', emoji: '🐦', color: '#1DA1F2', app: 'X', current_task: '' },
            { name: 'News', emoji: '📰', color: '#E74C3C', app: 'News', current_task: '' },
            { name: 'Gemini', emoji: '🔬', color: '#8E44AD', app: 'Gemini', current_task: '' },
        ];
        this.renderer.initAgents(this.agentsList);
        document.getElementById('agent-count').textContent = `${this.agentsList.length} agents`;
    }

    _setupWebSocket() {
        this.ws.on('connection', (data) => {
            const indicator = document.getElementById('connection-indicator');
            const text = document.getElementById('connection-text');

            if (data.status === 'connected') {
                indicator.className = 'indicator connected';
                text.textContent = 'Live';
                this.demo.stop();
                this.contextReporter = new ContextReporter(this.ws);
                // Re-fetch agents on reconnect
                this._loadAgents();
            } else {
                indicator.className = 'indicator disconnected';
                text.textContent = 'Reconnecting...';
                setTimeout(() => {
                    if (!this.ws.connected) {
                        text.textContent = 'Demo Mode';
                        this.demo.start();
                    }
                }, 3000);
            }
        });

        this.ws.on('message', (data) => this.handleMessage(data));
        this.ws.connect();

        setTimeout(() => {
            if (!this.ws.connected) {
                document.getElementById('connection-text').textContent = 'Demo Mode';
                this.demo.start();
            }
        }, 3000);
    }

    handleMessage(data) {
        const { sender, recipient, type, content, metadata } = data;

        // Check for permission requests
        if (metadata?.type === 'permission_request') {
            this.permissionUI.show(data);
        }

        // Assistant replies from the command pipeline
        if (metadata?.type === 'command_reply') {
            this.commandBar.handleReply(data);
        }

        switch (type) {
            case 'agent_update':
                this.renderer.updateAgent(sender, { current_task: content, status: 'working' });
                setTimeout(() => this.renderer.updateAgent(sender, { status: 'idle' }), 8000);
                this.feed.addItem(data);
                break;

            case 'agent_chat':
                this.renderer.showBubble(sender, content);
                if (recipient && recipient !== 'all') {
                    this.renderer.drawConnection(sender, recipient, metadata?.color);
                }
                this.feed.addItem(data);
                break;

            case 'discovery':
                this.renderer.showBubble(sender, content);
                this.renderer.updateAgent(sender, { status: 'working' });
                this.detail.addFinding(sender, content);
                this.feed.addItem(data);
                setTimeout(() => this.renderer.updateAgent(sender, { status: 'idle' }), 5000);
                break;

            case 'user_alert':
            case 'system':
            default:
                this.feed.addItem(data);
                break;
        }
    }
}

// ── Boot ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    window.app = new PhoneAgentsApp();

    // Register service worker for PWA
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
    }
});

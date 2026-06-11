class AgentsRenderer {
    constructor(container, svgOverlay) {
        this.container = container;
        this.svgOverlay = svgOverlay;
        this.agents = new Map();
        this.bubbles = [];
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.onAgentTap = null;

        window.addEventListener('resize', () => {
            this.width = window.innerWidth;
            this.height = window.innerHeight;
        });

        this._animationFrame = null;
        this._startDriftLoop();
    }

    initAgents(agentList) {
        // Place agents in a circular layout
        const cx = this.width / 2;
        const cy = this.height * 0.38;
        const radius = Math.min(this.width, this.height) * 0.28;

        agentList.forEach((agent, i) => {
            const angle = (i / agentList.length) * Math.PI * 2 - Math.PI / 2;
            const x = cx + Math.cos(angle) * radius;
            const y = cy + Math.sin(angle) * radius;

            const state = {
                ...agent,
                x,
                y,
                targetX: x,
                targetY: y,
                driftAngle: Math.random() * Math.PI * 2,
                driftSpeed: 0.002 + Math.random() * 0.003,
                driftRadius: 8 + Math.random() * 12,
                baseX: x,
                baseY: y,
                active: false,
                el: null,
            };

            this.agents.set(agent.name, state);
            this._createAgentElement(state);
        });
    }

    _createAgentElement(agent) {
        const node = document.createElement('div');
        node.className = 'agent-node';
        node.style.setProperty('--agent-color', agent.color);
        node.style.setProperty('--agent-color-alpha', agent.color + '40');

        // XSS-safe rendering
        const avatar = document.createElement('div');
        avatar.className = 'agent-avatar';
        avatar.textContent = agent.emoji;
        const nameEl = document.createElement('span');
        nameEl.className = 'agent-name';
        nameEl.textContent = agent.name;
        const statusEl = document.createElement('span');
        statusEl.className = 'agent-status-text';
        statusEl.textContent = agent.current_task || 'idle';
        node.appendChild(avatar);
        node.appendChild(nameEl);
        node.appendChild(statusEl);

        node.addEventListener('click', () => {
            if (this.onAgentTap) this.onAgentTap(agent.name);
        });

        node.style.transform = `translate(${agent.x - 40}px, ${agent.y - 40}px)`;
        this.container.appendChild(node);
        agent.el = node;
    }

    updateAgent(name, data) {
        const agent = this.agents.get(name);
        if (!agent) return;

        if (data.current_task !== undefined) {
            agent.current_task = data.current_task;
            const statusEl = agent.el.querySelector('.agent-status-text');
            if (statusEl) statusEl.textContent = data.current_task || 'idle';
        }

        if (data.status !== undefined) {
            agent.status = data.status;
            const isActive = data.status === 'working';
            agent.active = isActive;
            agent.el.classList.toggle('active', isActive);
        }
    }

    showBubble(senderName, content) {
        const agent = this.agents.get(senderName);
        if (!agent) return;

        const bubble = document.createElement('div');
        bubble.className = 'speech-bubble';
        bubble.textContent = content.length > 100 ? content.slice(0, 97) + '...' : content;

        const bx = agent.x - 20;
        const by = agent.y - 80;
        bubble.style.left = Math.max(10, Math.min(bx, this.width - 220)) + 'px';
        bubble.style.top = Math.max(60, by) + 'px';

        this.container.appendChild(bubble);

        setTimeout(() => {
            if (bubble.parentNode) bubble.parentNode.removeChild(bubble);
        }, 5500);
    }

    drawConnection(fromName, toName, color) {
        const from = this.agents.get(fromName);
        const to = this.agents.get(toName);
        if (!from || !to) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', from.x);
        line.setAttribute('y1', from.y);
        line.setAttribute('x2', to.x);
        line.setAttribute('y2', to.y);
        line.setAttribute('class', 'connection-line');
        line.setAttribute('stroke', color || '#ffffff30');
        line.setAttribute('stroke-dasharray', '4,4');

        this.svgOverlay.appendChild(line);

        setTimeout(() => {
            if (line.parentNode) line.parentNode.removeChild(line);
        }, 2200);
    }

    _startDriftLoop() {
        const drift = () => {
            const now = Date.now() / 1000;

            for (const [, agent] of this.agents) {
                agent.driftAngle += agent.driftSpeed;

                const dx = Math.cos(agent.driftAngle) * agent.driftRadius;
                const dy = Math.sin(agent.driftAngle * 0.7) * agent.driftRadius * 0.6;

                agent.x = agent.baseX + dx;
                agent.y = agent.baseY + dy;

                if (agent.el) {
                    agent.el.style.transform = `translate(${agent.x - 40}px, ${agent.y - 40}px)`;
                }
            }

            this._animationFrame = requestAnimationFrame(drift);
        };

        this._animationFrame = requestAnimationFrame(drift);
    }

    getAgentInfo(name) {
        return this.agents.get(name);
    }

    destroy() {
        if (this._animationFrame) {
            cancelAnimationFrame(this._animationFrame);
        }
    }
}

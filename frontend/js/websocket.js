class AgentWebSocket {
    constructor() {
        this.ws = null;
        this.listeners = {};
        this.reconnectDelay = 1000;
        this.maxReconnectDelay = 30000;
        this.connected = false;
        this.queue = [];
    }

    connect() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const token = (typeof AgentAuth !== 'undefined') ? AgentAuth.token() : '';
        const url = `${protocol}//${location.host}/ws` +
            (token ? `?token=${encodeURIComponent(token)}` : '');

        try {
            this.ws = new WebSocket(url);
        } catch (e) {
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            this.connected = true;
            this.reconnectDelay = 1000;
            this._emit('connection', { status: 'connected' });

            // Flush queued messages
            while (this.queue.length > 0) {
                const msg = this.queue.shift();
                this.ws.send(JSON.stringify(msg));
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._emit('message', data);
                if (data.type) {
                    this._emit(data.type, data);
                }
            } catch (e) {
                console.error('Failed to parse WebSocket message:', e);
            }
        };

        this.ws.onclose = () => {
            this.connected = false;
            this._emit('connection', { status: 'disconnected' });
            this._scheduleReconnect();
        };

        this.ws.onerror = () => {
            this.connected = false;
        };
    }

    send(data) {
        if (this.connected && this.ws) {
            this.ws.send(JSON.stringify(data));
        } else {
            this.queue.push(data);
        }
    }

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    _emit(event, data) {
        const callbacks = this.listeners[event] || [];
        for (const cb of callbacks) {
            try {
                cb(data);
            } catch (e) {
                console.error(`Error in ${event} listener:`, e);
            }
        }
    }

    _scheduleReconnect() {
        setTimeout(() => {
            this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay);
            this.connect();
        }, this.reconnectDelay);
    }
}

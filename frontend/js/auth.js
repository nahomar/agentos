// ============================================================
// AgentOS — Client auth
// Open the app as http://<host>:8000/?token=<api_token> once;
// the token is stored locally and stripped from the URL bar.
// ============================================================

const AgentAuth = {
    _key: 'agentos_token',

    token() {
        const urlToken = new URLSearchParams(location.search).get('token');
        if (urlToken) {
            localStorage.setItem(this._key, urlToken);
            const url = new URL(location.href);
            url.searchParams.delete('token');
            history.replaceState(null, '', url.pathname + (url.search || ''));
        }
        return localStorage.getItem(this._key) || '';
    },

    fetch(input, init = {}) {
        const token = this.token();
        init.headers = Object.assign(
            {},
            init.headers,
            token ? { 'Authorization': `Bearer ${token}` } : {}
        );
        return fetch(input, init);
    },
};

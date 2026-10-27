// Synthetic backend FriendSnapshot responses from the public HTTP protocol
// Delays expose accidental serialization in the real authenticated Python client.
const http = require('node:http');
let active = 0, peak = 0, completed = 0, invalid = 0;
http.createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost');
  const reply = (status, body) => {
    res.writeHead(status, {'Content-Type': 'application/json'});
    res.end(JSON.stringify(body));
  };
  if (url.pathname === '/reset' && req.method === 'POST') {
    active = peak = completed = invalid = 0;
    return reply(200, {ok: true});
  }
  if (url.pathname === '/stats') return reply(200, {peak, completed, invalid});
  const match = url.pathname.match(/^\/v1\/friends\/(you|friend\d+)$/);
  if (!match || req.method !== 'GET') return reply(501, {error: 'not_modeled'});
  if (url.searchParams.get('cursus_id') !== '21' ||
      url.searchParams.get('include_xp') !== 'false' ||
      url.searchParams.get('refresh') !== 'true' || !req.headers.dpop) {
    invalid++;
    return reply(400, {error: 'invalid_query'});
  }
  active++;
  peak = Math.max(peak, active);
  const login = match[1];
  setTimeout(() => {
    const stamp = new Date().toISOString();
    active--;
    completed++;
    reply(200, {
      user_id: login === 'you' ? '42' : String(100 + Number(login.slice(6))),
      login, display_name: login, cursus_id: 21, level: 8.42, grade: 'Learner',
      campuses: [{id: 31, name: 'Paris', is_primary: true}],
      location: null, presence: {status: 'available', cached_at: stamp},
      items: [], meta: {cache: 'fresh', stale: false, cached_at: stamp}
    });
  }, 150);
}).listen(process.env.PORT);

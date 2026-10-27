// Synthetic backend responses from session.routes.ts, dpop-auth.ts and profile.service.ts.
// Scenario prefixes let each test use its own backend base URL without shared state.
const http = require('node:http');
http.createServer((req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  const match = path.match(/^\/(expired|renewable|outage|revoked|reauthorize)(\/v1\/.*)$/);
  res.setHeader('Content-Type', 'application/json');
  const reply = (status, body) => { res.statusCode = status; res.end(JSON.stringify(body)); };
  if (!match) return reply(501, {error: 'not_modeled'});
  const [, scenario, route] = match;
  if (scenario === 'outage') return reply(503, {error: 'session_service_unavailable'});
  if (route === '/v1/sessions/refresh' && req.method === 'POST') {
    if (scenario === 'expired') return reply(401, {error: 'invalid_device_credentials'});
    return reply(200, {access_token: 'b'.repeat(43), refresh_token: 's'.repeat(43), expires_at: '2099-01-01T00:00:00Z'});
  }
  if (req.method === 'GET' && (route === '/v1/me' || route === '/v1/cursuses')) {
    if (scenario === 'revoked') return reply(401, {error: 'invalid_device_credentials'});
    if (scenario === 'reauthorize') return reply(401, {error: 'reauthorization_required', reauthorization_required: true});
    return reply(200, route === '/v1/me' ? {account_id: '42', login: 'synthetic-student', campuses: []} : {cursuses: []});
  }
  reply(501, {error: 'not_modeled'});
}).listen(process.env.PORT);

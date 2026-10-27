// Narrow transport fixture derived from the public HTTP protocol
// The real service's consent/adjacency rules are tested in backend/test/social.
const http = require('node:http');
const alice = {account_id:'1',login:'alice'}, bob = {account_id:'2',login:'bob'}, charlie = {account_id:'3',login:'charlie'};
function seed() {
 const now = new Date().toISOString();
 return {account_id:'1',dnd:false,friends:[bob],incoming:[{id:'1:3',members:[alice,charlie],requested_by:'3',status:'pending',created_at:now}],outgoing:[],pokes:[{id:'11111111-1111-4111-8111-111111111111',recipient:alice,senders:[bob],approved:['2'],message:'[bold]Lunch?[/bold]',status:'sent',created_at:now,expires_at:new Date(Date.now()+86400000).toISOString(),dismissed:false}]};
}
http.createServer((req,res)=>{
 const url=new URL(req.url,'http://localhost');
 const reply=(code,value)=>{res.writeHead(code,{'Content-Type':'application/json'});res.end(JSON.stringify(value));};
 let state=pm.state.get('social-backend:state');if(!state){state=seed();pm.state.set('social-backend:state',state);}
 if(url.pathname==='/v1/events'&&req.method==='GET'){
  res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-store'});
  res.write('event: ready\ndata: resync\n\n');
  setTimeout(()=>res.end('event: changed\ndata: social\n\n'),100);return;
 }
 if(url.pathname==='/v1/social'&&req.method==='GET')return reply(200,state);
 if(url.pathname==='/v1/social/neighbours'&&req.method==='GET')return reply(200,{items:[]});
 if(url.pathname==='/v1/social/actions'&&req.method==='POST'){
  const v=req.body;
  if(v.action==='accept'&&v.account_id==='3'){state.incoming=[];if(!state.friends.some(f=>f.account_id==='3'))state.friends.push(charlie);}
  else if(v.action==='dismiss'){state.pokes=state.pokes.filter(p=>p.id!==v.id);}
  else return reply(501,{error:'fixture_action_not_modeled'});
  pm.state.set('social-backend:state',state);return reply(200,{ok:true});
 }
 reply(501,{error:'fixture_endpoint_not_modeled'});
}).listen(process.env.PORT);

import express from 'express';
import {createDocument, normalizeDocument} from '../../src/index.js';
const app=express();let page=createDocument({title:'Página Express'});app.use(express.json({limit:'2mb'}));app.use('/builder',express.static(new URL('../../',import.meta.url).pathname));
app.get('/api/pages/home',(_req,res)=>res.json({data:{document:page}}));
app.post('/api/pages/home/draft',(req,res)=>{page=normalizeDocument(req.body);res.json({data:{saved:true}})});
app.post('/api/pages/home/autosave',(req,res)=>{page=normalizeDocument(req.body);res.json({data:{saved:true}})});
app.post('/api/pages/home/publish',(_req,res)=>res.json({data:{published:true}}));
app.listen(3000,()=>console.log('http://localhost:3000'));

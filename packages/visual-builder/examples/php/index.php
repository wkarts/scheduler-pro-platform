<?php
$storage = __DIR__ . '/page.json';
$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';
$path = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (str_starts_with($path, '/api/page')) {
    header('Content-Type: application/json; charset=utf-8');
    if ($method === 'GET') {
        $document = is_file($storage) ? json_decode(file_get_contents($storage), true) : [
            'schema'=>'argws-visual-builder/v3','version'=>4,'surface'=>'PAGE','title'=>'Página PHP',
            'settings'=>['language'=>'pt-BR'],'global_styles'=>[],'design_system'=>['breakpoints'=>[],'variables'=>[],'classes'=>[]],
            'seo'=>[],'project'=>[],'builder'=>['schema'=>'argws-visual-builder/v3','root_ids'=>[],'nodes'=>(object)[]],'blocks'=>[],
        ];
        echo json_encode(['data'=>['document'=>$document]], JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES); exit;
    }
    if (in_array($method, ['POST','PUT'], true)) {
        $payload = json_decode(file_get_contents('php://input'), true, 512, JSON_THROW_ON_ERROR);
        $schema = $payload['builder']['schema'] ?? $payload['schema'] ?? '';
        if (!in_array($schema, ['argws-visual-builder/v1','argws-visual-builder/v2','argws-visual-builder/v3'], true)) { http_response_code(422); echo json_encode(['error'=>'schema inválido']); exit; }
        file_put_contents($storage, json_encode($payload, JSON_PRETTY_PRINT|JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR), LOCK_EX);
        echo json_encode(['data'=>['saved'=>true]]); exit;
    }
}
?>
<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="../../styles/builder.css"><title>ARGWS Builder PHP</title></head><body>
<argws-visual-builder id="builder"></argws-visual-builder>
<script type="module">
import {RestAdapter} from '../../src/index.js';
const el=document.getElementById('builder');el.adapter=new RestAdapter({loadUrl:'/api/page',draftUrl:'/api/page',autosaveUrl:'/api/page',publishUrl:'/api/page'});await el.load();
</script></body></html>

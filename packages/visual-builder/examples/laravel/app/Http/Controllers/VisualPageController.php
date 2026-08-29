<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Storage;
use Illuminate\View\View;

class VisualPageController extends Controller
{
    private function assertSlug(string $slug): string
    {
        abort_unless((bool) preg_match('/^[a-z0-9][a-z0-9-]{0,118}[a-z0-9]$/', $slug), 404);

        return $slug;
    }

    private function path(string $slug, string $state = 'draft'): string
    {
        return sprintf('visual-builder/pages/%s.%s.json', $this->assertSlug($slug), $state);
    }

    private function defaultDocument(): array
    {
        return [
            'schema' => 'argws-visual-builder/v3',
            'version' => 4,
            'surface' => 'PAGE',
            'title' => 'Nova página',
            'settings' => [
                'content_width' => 1180,
                'page_layout' => 'full-width',
                'custom_css' => '',
                'language' => 'pt-BR',
            ],
            'global_styles' => [
                'primary' => '#3151cf',
                'secondary' => '#151c31',
                'accent' => '#6d72ef',
                'background' => '#ffffff',
                'text' => '#1d273a',
                'heading_font' => 'Inter',
                'body_font' => 'Inter',
                'radius' => 16,
            ],
            'design_system' => [
                'breakpoints' => [
                    ['id' => 'desktop', 'label' => 'Desktop', 'max' => null, 'canvas' => 1180],
                    ['id' => 'tablet', 'label' => 'Tablet', 'max' => 1024, 'canvas' => 820],
                    ['id' => 'mobile', 'label' => 'Mobile', 'max' => 680, 'canvas' => 390],
                ],
                'variables' => [],
                'classes' => [],
            ],
            'seo' => [
                'title' => '',
                'description' => '',
                'share_image' => '',
                'canonical' => '',
                'robots' => 'index,follow',
                'open_graph' => [],
                'twitter' => [],
                'structured_data' => [],
            ],
            'project' => [
                'capabilities' => [],
                'assets' => ['fonts' => [], 'icons' => [], 'media' => []],
                'custom_code' => [],
                'data_requirements' => [],
                'i18n' => ['default_locale' => 'pt-BR', 'locales' => ['pt-BR'], 'translations' => []],
                'permissions' => ['roles' => []],
                'collaboration' => ['revision' => 0],
                'integrations' => [],
            ],
            'builder' => [
                'schema' => 'argws-visual-builder/v3',
                'root_ids' => [],
                'nodes' => (object) [],
            ],
            'blocks' => [],
        ];
    }

    public function editor(string $slug): View
    {
        $this->assertSlug($slug);

        return view('visual-builder', ['slug' => $slug]);
    }

    public function show(string $slug): JsonResponse
    {
        $path = $this->path($slug);
        $disk = Storage::disk('local');
        $document = $disk->exists($path)
            ? json_decode($disk->get($path), true, 512, JSON_THROW_ON_ERROR)
            : $this->defaultDocument();

        return response()->json(['data' => ['document' => $document]]);
    }

    public function draft(Request $request, string $slug): JsonResponse
    {
        $document = $request->json()->all();
        $schema = data_get($document, 'builder.schema', data_get($document, 'schema'));

        abort_unless(
            in_array($schema, ['argws-visual-builder/v1', 'argws-visual-builder/v2', 'argws-visual-builder/v3'], true),
            422,
            'Documento do builder inválido.'
        );

        Storage::disk('local')->put(
            $this->path($slug),
            json_encode($document, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT | JSON_THROW_ON_ERROR)
        );

        return response()->json(['data' => ['saved' => true]]);
    }

    public function publish(string $slug): JsonResponse
    {
        $disk = Storage::disk('local');
        $draft = $this->path($slug);

        abort_unless($disk->exists($draft), 409, 'Salve o rascunho antes de publicar.');
        $disk->put($this->path($slug, 'published'), $disk->get($draft));

        return response()->json(['data' => ['published' => true]]);
    }
}

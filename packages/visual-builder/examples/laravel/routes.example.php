<?php

use App\Http\Controllers\VisualPageController;
use Illuminate\Support\Facades\Route;

Route::middleware(['web', 'auth'])->group(function (): void {
    Route::get('/visual-builder/{slug}', [VisualPageController::class, 'editor']);
    Route::get('/api/pages/{slug}', [VisualPageController::class, 'show']);
    Route::post('/api/pages/{slug}/draft', [VisualPageController::class, 'draft']);
    Route::post('/api/pages/{slug}/autosave', [VisualPageController::class, 'draft']);
    Route::post('/api/pages/{slug}/publish', [VisualPageController::class, 'publish']);
});

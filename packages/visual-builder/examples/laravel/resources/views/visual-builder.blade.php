<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">
    <title>ARGWS Visual Builder</title>
    <link rel="stylesheet" href="{{ asset('vendor/argws-visual-builder/styles/builder.css') }}">
</head>
<body>
    <argws-visual-builder id="visual-builder"></argws-visual-builder>

    <script type="module">
        import {
            RestAdapter,
        } from '{{ asset('vendor/argws-visual-builder/src/index.js') }}';

        const csrf = document.querySelector('meta[name="csrf-token"]').content;
        const builder = document.querySelector('#visual-builder');

        builder.adapter = new RestAdapter({
            baseUrl: '/api/pages',
            slug: @json($slug),
            headers: () => ({
                'X-CSRF-TOKEN': csrf,
                'X-Requested-With': 'XMLHttpRequest',
            }),
        });

        await builder.load();
    </script>
</body>
</html>

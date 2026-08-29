<link rel="stylesheet" href="{{ asset('vendor/argws-visual-builder/styles/builder.css') }}">
<argws-page-renderer id="argws-page"></argws-page-renderer>
<script type="module">
import '{{ asset('vendor/argws-visual-builder/src/index.js') }}';
const response = await fetch(@json(route('visual-pages.show', ['slug' => $slug])), {headers:{Accept:'application/json'}});
const payload = await response.json();
document.getElementById('argws-page').document = payload.data?.document ?? payload.document ?? payload;
</script>

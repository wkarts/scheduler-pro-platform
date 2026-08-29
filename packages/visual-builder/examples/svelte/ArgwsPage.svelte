<script>
  import '@argws/visual-builder';
  import '@argws/visual-builder/styles.css';
  import {onMount} from 'svelte';
  export let documentUrl='/api/pages/home'; let host;
  onMount(async()=>{const r=await fetch(documentUrl);const p=await r.json();host.document=p.data?.document??p.document??p;});
</script>
<argws-page-renderer bind:this={host}></argws-page-renderer>

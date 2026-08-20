<script lang="ts">
	import { onMount } from 'svelte';
	import { WEBUI_NAME, showSidebar } from '$lib/stores';

	// Hide sidebar when hearth loads — this is the living room, not the office
	onMount(() => {
		showSidebar.set(false);
	});
</script>

<svelte:head>
	<title>Home / {$WEBUI_NAME}</title>
</svelte:head>

<div class="flex flex-col w-full h-screen max-h-[100dvh]">
	<div class="flex-1 max-h-full overflow-y-auto">
		<slot />
	</div>
</div>

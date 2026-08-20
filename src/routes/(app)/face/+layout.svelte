<script lang="ts">
	import { WEBUI_NAME } from '$lib/stores';
</script>

<svelte:head>
	<title>Greg / {$WEBUI_NAME}</title>
</svelte:head>

<div class="face-layout">
	<slot />
</div>

<style>
	.face-layout {
		width: 100vw;
		height: 100vh;
		overflow: hidden;
		background: #000;
		cursor: none;
		user-select: none;
		-webkit-user-select: none;
	}

	/* Show cursor on mouse movement, hide after 3s idle */
	.face-layout:hover {
		cursor: default;
	}
</style>

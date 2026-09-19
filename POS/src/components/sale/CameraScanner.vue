<template>
	<!-- Camera Scanner: Mobile = full-screen overlay, Desktop = floating PiP -->
	<div
		v-if="active"
		:class="[
			isMobile
				? 'fixed inset-0 z-[9999] flex flex-col bg-black'
				: 'contents'
		]"
		@keyup.esc="close"
		tabindex="0"
		ref="rootEl"
	>
		<!-- Mobile: full-screen camera -->
		<template v-if="isMobile">
			<!-- Top bar -->
			<div class="absolute top-0 inset-x-0 z-20 flex items-center justify-between px-4 py-3 bg-gradient-to-b from-black/60 to-transparent">
				<span class="text-white text-sm font-medium">
					{{ __("Scan Barcode / QR Code") }}
				</span>
				<div class="flex items-center gap-2">
					<button
						@click="toggleTorch"
						class="p-2 rounded-full bg-white/20 backdrop-blur-sm text-white active:bg-white/30"
						:aria-label="__('Toggle flashlight')"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
								d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
						</svg>
					</button>
					<button
						@click="close"
						class="p-2 rounded-full bg-white/20 backdrop-blur-sm text-white active:bg-white/30"
						:aria-label="__('Close scanner')"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>

			<!-- Camera video element -->
			<video
				ref="videoEl"
				class="absolute inset-0 w-full h-full object-cover"
				autoplay
				playsinline
				muted
			/>

			<!-- Scan line animation -->
			<div class="absolute inset-x-0 top-1/2 -translate-y-1/2 z-10 pointer-events-none">
				<div class="mx-auto w-3/4 h-0.5 bg-red-500/80 shadow-[0_0_8px_rgba(239,68,68,0.6)] scanner-line" />
			</div>

			<!-- Bottom info -->
			<div class="absolute bottom-0 inset-x-0 z-20 bg-gradient-to-t from-black/60 to-transparent pt-8 pb-6 px-4">
				<p class="text-white/80 text-xs text-center">
					{{ __("Point camera at barcode or QR code") }}
				</p>
				<!-- Last scanned feedback -->
				<div
					v-if="lastScanned"
					class="mt-2 mx-auto max-w-xs bg-green-500/90 backdrop-blur-sm rounded-lg px-3 py-2 text-center animate-pulse-once"
				>
					<p class="text-white text-sm font-medium truncate">{{ lastScanned }}</p>
				</div>
			</div>
		</template>

		<!-- Desktop: floating draggable PiP panel (doesn't block POS) -->
		<template v-else>
			<div
				ref="pipPanel"
				class="fixed z-[9999] w-[360px] bg-gray-900 rounded-2xl shadow-2xl border border-gray-700 overflow-hidden select-none"
				:style="{ left: pipX + 'px', top: pipY + 'px', bottom: 'auto', right: 'auto' }"
			>
				<!-- Draggable header -->
				<div
					class="flex items-center justify-between px-3 py-2 bg-gray-800 border-b border-gray-700 cursor-move"
					@mousedown="startDrag"
					@touchstart.passive="startDrag"
				>
					<div class="flex items-center gap-2">
						<!-- Drag handle icon -->
						<svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 24 24">
							<circle cx="9" cy="5" r="1.5" /><circle cx="15" cy="5" r="1.5" />
							<circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
							<circle cx="9" cy="19" r="1.5" /><circle cx="15" cy="19" r="1.5" />
						</svg>
						<div class="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
						<span class="text-white text-xs font-medium">{{ __("Camera Scanner") }}</span>
					</div>
					<div class="flex items-center gap-1">
						<button
							@click.stop="toggleTorch"
							class="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
							:aria-label="__('Toggle flashlight')"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
							</svg>
						</button>
						<button
							@click.stop="close"
							class="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
							:aria-label="__('Close scanner')"
						>
							<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
							</svg>
						</button>
					</div>
				</div>

				<!-- Camera feed -->
				<div class="relative aspect-[4/3] bg-black">
					<video
						ref="videoEl"
						class="w-full h-full object-cover"
						autoplay
						playsinline
						muted
					/>
					<!-- Scan line -->
					<div class="absolute inset-x-0 top-1/2 -translate-y-1/2 pointer-events-none">
						<div class="mx-4 h-0.5 bg-red-500/80 shadow-[0_0_6px_rgba(239,68,68,0.5)] scanner-line" />
					</div>
					<!-- Corner brackets -->
					<div class="absolute inset-4 pointer-events-none">
						<div class="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 border-white/60 rounded-tl-lg" />
						<div class="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 border-white/60 rounded-tr-lg" />
						<div class="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 border-white/60 rounded-bl-lg" />
						<div class="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 border-white/60 rounded-br-lg" />
					</div>
					<!-- Error overlay inside panel -->
					<div v-if="error" class="absolute inset-0 flex items-center justify-center bg-gray-900/90">
						<div class="text-center px-4">
							<svg class="mx-auto h-8 w-8 text-red-400 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
									d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
							</svg>
							<p class="text-white text-xs font-medium mb-1">{{ __("Camera Error") }}</p>
							<p class="text-gray-400 text-[10px] mb-2">{{ error }}</p>
							<button
								@click.stop="retry"
								class="px-3 py-1 bg-white/10 hover:bg-white/20 text-white text-[10px] rounded transition-colors"
							>
								{{ __("Retry") }}
							</button>
						</div>
					</div>
				</div>

				<!-- Status bar -->
				<div class="px-3 py-2 bg-gray-800 flex items-center justify-between">
					<p class="text-gray-400 text-[11px]">{{ __("Point at barcode to scan") }}</p>
					<p v-if="lastScanned" class="text-green-400 text-[11px] font-mono truncate max-w-[180px]">
						{{ lastScanned }}
					</p>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup>
import { ref, watch, onUnmounted, nextTick } from "vue";

const props = defineProps({
	active: { type: Boolean, default: false },
});

const emit = defineEmits(["scan", "close"]);

const rootEl = ref(null);
const videoEl = ref(null);
const pipPanel = ref(null);
const error = ref(null);
const lastScanned = ref(null);
const isMobile = ref(false);
const torchOn = ref(false);

// ---- Desktop PiP drag state ----
const PANEL_W = 360;
const PANEL_H = 340; // approximate
const pipX = ref(0);
const pipY = ref(0);
let dragging = false;
let dragStartX = 0;
let dragStartY = 0;
let panelStartX = 0;
let panelStartY = 0;

function positionPip() {
	// Default: bottom-right corner
	pipX.value = window.innerWidth - PANEL_W - 16;
	pipY.value = window.innerHeight - PANEL_H - 16;
}

function startDrag(e) {
	const touch = e.touches ? e.touches[0] : e;
	dragging = true;
	dragStartX = touch.clientX;
	dragStartY = touch.clientY;
	panelStartX = pipX.value;
	panelStartY = pipY.value;
	document.addEventListener("mousemove", onDrag);
	document.addEventListener("mouseup", stopDrag);
	document.addEventListener("touchmove", onDrag, { passive: false });
	document.addEventListener("touchend", stopDrag);
	e.preventDefault();
}

function onDrag(e) {
	if (!dragging) return;
	const touch = e.touches ? e.touches[0] : e;
	const dx = touch.clientX - dragStartX;
	const dy = touch.clientY - dragStartY;
	const maxX = window.innerWidth - PANEL_W;
	const maxY = window.innerHeight - PANEL_H;
	pipX.value = Math.max(0, Math.min(maxX, panelStartX + dx));
	pipY.value = Math.max(0, Math.min(maxY, panelStartY + dy));
}

function stopDrag() {
	dragging = false;
	document.removeEventListener("mousemove", onDrag);
	document.removeEventListener("mouseup", stopDrag);
	document.removeEventListener("touchmove", onDrag);
	document.removeEventListener("touchend", stopDrag);
	// Save position
	try {
		localStorage.setItem("posnext:camera-pip", JSON.stringify({ x: pipX.value, y: pipY.value }));
	} catch {}
}

let stream = null;
let detector = null;
let scanFrame = null;
let lastScanTime = 0;
const SCAN_COOLDOWN_MS = 800; // debounce: same barcode won't re-trigger within 800ms
const lastCode = ref("");

// ---- Detection ----

async function startScanning() {
	error.value = null;

	// Detect mobile
	isMobile.value = /Android|iPhone|iPad|iPod|webOS/i.test(navigator.userAgent)
		|| (navigator.maxTouchPoints > 0 && window.innerWidth < 768);

	// Position desktop PiP panel
	if (!isMobile.value) {
		try {
			const saved = JSON.parse(localStorage.getItem("posnext:camera-pip") || "null");
			if (saved && typeof saved.x === "number" && typeof saved.y === "number") {
				pipX.value = Math.max(0, Math.min(window.innerWidth - PANEL_W, saved.x));
				pipY.value = Math.max(0, Math.min(window.innerHeight - PANEL_H, saved.y));
			} else {
				positionPip();
			}
		} catch {
			positionPip();
		}
	}

	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: {
				facingMode: "environment",
				width: { ideal: 1280 },
				height: { ideal: 720 },
			},
			audio: false,
		});

		if (videoEl.value) {
			videoEl.value.srcObject = stream;
			await videoEl.value.play();
		}

		// Use native BarcodeDetector API (Chrome, Edge, Android, Opera)
		if ("BarcodeDetector" in window) {
			try {
				const supported = await BarcodeDetector.getSupportedFormats();
				detector = new BarcodeDetector({
					formats: supported.length > 0 ? supported : [
						"ean_13", "ean_8", "upc_a", "upc_e",
						"code_128", "code_39", "code_93",
						"qr_code", "data_matrix", "itf",
						"codabar",
					],
				});
			} catch {
				detector = null;
			}
		}

		scanLoop();
	} catch (err) {
		if (err.name === "NotAllowedError") {
			error.value = "Camera permission was denied. Please allow camera access in your browser settings and try again.";
		} else if (err.name === "NotFoundError") {
			error.value = "No camera found on this device.";
		} else {
			error.value = err.message || "Could not access camera.";
		}
	}
}

async function scanLoop() {
	if (!videoEl.value || !props.active) return;

	try {
		let result = null;

		// Native BarcodeDetector
		if (detector && detector.detect) {
			const barcodes = await detector.detect(videoEl.value);
			if (barcodes && barcodes.length > 0) {
				result = barcodes[0].rawValue;
			}
		}

		if (result) {
			const now = Date.now();
			if (result !== lastCode.value || now - lastScanTime > SCAN_COOLDOWN_MS) {
				lastCode.value = result;
				lastScanTime = now;
				lastScanned.value = result;
				emit("scan", result);

				// Clear feedback after 2s
				setTimeout(() => {
					if (lastScanned.value === result) {
						lastScanned.value = null;
					}
				}, 2000);
			}
		}
	} catch {
		// Scan frame error — continue
	}

	if (props.active) {
		scanFrame = requestAnimationFrame(scanLoop);
	}
}

async function toggleTorch() {
	if (!stream) return;
	const track = stream.getVideoTracks()[0];
	if (!track) return;

	const capabilities = track.getCapabilities?.();
	if (!capabilities?.torch) return;

	torchOn.value = !torchOn.value;
	try {
		await track.applyConstraints({
			advanced: [{ torch: torchOn.value }],
		});
	} catch {
		// Torch not supported
	}
}

function retry() {
	stop();
	nextTick(() => startScanning());
}

function stop() {
	if (scanFrame) {
		cancelAnimationFrame(scanFrame);
		scanFrame = null;
	}
	if (stream) {
		stream.getTracks().forEach((t) => t.stop());
		stream = null;
	}
	detector = null;
	lastScanned.value = null;
	lastCode.value = "";
	torchOn.value = false;
}

function close() {
	stop();
	emit("close");
}

watch(
	() => props.active,
	(active) => {
		if (active) {
			nextTick(() => startScanning());
			// Focus the root for keyboard events (Esc to close)
			nextTick(() => rootEl.value?.focus());
		} else {
			stop();
		}
	}
);

onUnmounted(() => {
	stop();
	stopDrag(); // clean up any lingering drag listeners
});
</script>

<style scoped>
/* Scan line animation */
.scanner-line {
	animation: scan-sweep 2s ease-in-out infinite;
}

@keyframes scan-sweep {
	0%, 100% { transform: translateY(-60px); }
	50% { transform: translateY(60px); }
}

/* One-time pulse for scan feedback */
.animate-pulse-once {
	animation: pulse-once 0.6s ease-out;
}

@keyframes pulse-once {
	0% { transform: scale(0.95); opacity: 0.7; }
	50% { transform: scale(1.02); }
	100% { transform: scale(1); opacity: 1; }
}
</style>

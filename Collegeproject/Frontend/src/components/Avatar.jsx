import { useEffect, useRef } from "react";
import { useGLTF, useAnimations } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

// Confirmed morph target names from backup_head_with_cloth.glb
const VISEME_MAP = {
    A: "pp",
    B: "kk",
    C: "ih",
    D: "AA",
    E: "oh",
    F: "ou",
    G: "FF",
    H: "TH",
    X: "sil",
};

const HEAD_MESH_NAME = "GEO-rain-head";

const Avatar = (props) => {
    const { scene, nodes, animations } = useGLTF("models/backup_head_with_cloth.glb");
    const { actions } = useAnimations(animations, scene);

    const headMeshRef   = useRef(null);
    const analyserRef   = useRef(null);
    const dataArrayRef  = useRef(null);
    const audioCtxRef   = useRef(null);
    const audioRef      = useRef(null);    // the <Audio> element
    const activeViseme  = useRef("X");

    // ── 1. Discover head mesh directly by name ───────────────────────────────
    useEffect(() => {
        if (nodes[HEAD_MESH_NAME]) {
            headMeshRef.current = nodes[HEAD_MESH_NAME];
            const dict = nodes[HEAD_MESH_NAME].morphTargetDictionary || {};
            console.log("[Avatar] ✅ Head mesh found:", HEAD_MESH_NAME);
            console.log("[Avatar] Morph keys:", Object.keys(dict).join(", "));
        } else {
            // Fallback: traverse
            scene.traverse((obj) => {
                if (obj.isSkinnedMesh && obj.morphTargetDictionary) {
                    if ("sil" in obj.morphTargetDictionary || "pp" in obj.morphTargetDictionary) {
                        headMeshRef.current = obj;
                        console.log("[Avatar] ✅ Found via traverse:", obj.name);
                    }
                }
            });
        }
    }, [nodes, scene]);

    // ── 2. TTS + AudioContext setup ──────────────────────────────────────────
    useEffect(() => {
        const onSpeak = async ({ detail: { text } }) => {
            if (!text) return;
            // Stop previous audio
            if (audioRef.current) {
                audioRef.current.pause();
                audioRef.current = null;
            }

            try {
                const base = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
                const res  = await fetch(`${base}/api/gemini/tts/?text=${encodeURIComponent(text)}`);
                if (!res.ok) throw new Error(`TTS HTTP ${res.status}`);

                const blob  = await res.blob();
                const url   = URL.createObjectURL(blob);
                const audio = new Audio(url);
                audioRef.current  = audio;         // store so useFrame can check .paused

                // AudioContext analyser for accurate frequency-based lipsync
                try {
                    if (!audioCtxRef.current) {
                        audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
                    }
                    const ctx = audioCtxRef.current;
                    if (ctx.state === "suspended") {
                        ctx.resume().catch(e => console.warn("AudioContext resume rejected:", e));
                    }

                    const src      = ctx.createMediaElementSource(audio);
                    const analyser = ctx.createAnalyser();
                    analyser.fftSize = 256;
                    src.connect(analyser);
                    analyser.connect(ctx.destination);
                    analyserRef.current  = analyser;
                    dataArrayRef.current = new Uint8Array(analyser.frequencyBinCount);
                    console.log("[Avatar] 🎛️ Analyser connected");
                } catch (e) {
                    console.warn("[Avatar] AudioContext N/A (timer fallback active):", e.message);
                    analyserRef.current  = null;
                    dataArrayRef.current = null;
                }

                audio.addEventListener("play",  () => {
                    console.log("[Avatar] 🎤 Audio playing");
                    window.dispatchEvent(new CustomEvent("avatar-speaking-start"));
                });
                audio.addEventListener("ended", () => {
                    console.log("[Avatar] 🔇 Audio ended");
                    activeViseme.current = "X";
                    window.dispatchEvent(new CustomEvent("avatar-speaking-end"));
                });
                audio.addEventListener("error", () => {
                    window.dispatchEvent(new CustomEvent("avatar-speaking-end"));
                });

                await audio.play();
            } catch (err) {
                console.error("[Avatar] Error:", err);
                window.dispatchEvent(new CustomEvent("avatar-speaking-end"));
            }
        };

        window.addEventListener("speak-text", onSpeak);
        return () => {
            window.removeEventListener("speak-text", onSpeak);
            if (audioRef.current) audioRef.current.pause();
        };
    }, []);

    // ── 3. Per-frame lipsync ──────────────────────────────────────────────────
    useFrame((state) => {
        const mesh = headMeshRef.current;
        if (!mesh?.morphTargetInfluences || !mesh?.morphTargetDictionary) return;

        const inf  = mesh.morphTargetInfluences;
        const dict = mesh.morphTargetDictionary;
        const t    = state.clock.elapsedTime;

        // ── CHECK AUDIO STATE DIRECTLY every frame (most reliable) ───────────
        const audio       = audioRef.current;
        const isPlaying   = audio != null &&
                            !audio.paused   &&
                            !audio.ended    &&
                            audio.currentTime > 0 &&
                            audio.readyState >= 2;

        if (isPlaying) {
            let gotRealData = false;

            // Frequency-based visemes (if analyser available)
            if (analyserRef.current && dataArrayRef.current) {
                analyserRef.current.getByteFrequencyData(dataArrayRef.current);
                const d = dataArrayRef.current;
                const n = d.length;
                const avg = (lo, hi) => {
                    let s = 0, c = 0;
                    for (let i = Math.floor(n * lo); i < Math.floor(n * hi); i++) { s += d[i]; c++; }
                    return c ? s / c : 0;
                };
                const bL = avg(0.00, 0.25);
                const bM = avg(0.25, 0.55);
                const bH = avg(0.55, 0.85);
                const mx = Math.max(bL, bM, bH);

                if (mx > 5) {
                    gotRealData = true;
                    if      (bL > bM && bL > bH) activeViseme.current = bL > 50 ? "D" : bL > 25 ? "E" : "A";
                    else if (bM > bH)             activeViseme.current = "C";
                    else                          activeViseme.current = "H";
                }
            }

            // Timer-based fallback — guaranteed visible mouth animation
            if (!gotRealData) {
                const phase = t % 0.5;
                if      (phase < 0.13) activeViseme.current = "D";   // AA — wide open
                else if (phase < 0.26) activeViseme.current = "F";   // ou — round
                else if (phase < 0.38) activeViseme.current = "E";   // oh
                else                   activeViseme.current = "A";   // pp — soft
            }

        } else {
            activeViseme.current = "X";  // silence
        }

        // ── Apply morphs ─────────────────────────────────────────────────────
        // Fade all viseme morphs toward 0
        for (const morph of Object.values(VISEME_MAP)) {
            const idx = dict[morph];
            if (idx !== undefined) inf[idx] = THREE.MathUtils.lerp(inf[idx], 0, 0.3);
        }

        // Drive active viseme toward target value
        const targetMorph = VISEME_MAP[activeViseme.current];
        const targetValue = activeViseme.current === "X" ? 0 : 0.9;
        if (targetMorph && dict[targetMorph] !== undefined) {
            inf[dict[targetMorph]] = THREE.MathUtils.lerp(inf[dict[targetMorph]], targetValue, 0.5);
        }

        // ── Blink every 4.5s ─────────────────────────────────────────────────
        const blinkL = dict["EyelidsClose.L"];
        const blinkR = dict["EyelidsClose.R"];
        if (blinkL !== undefined) {
            const blink = (t % 4.5) > 4.3 ? 1 : 0;
            inf[blinkL] = THREE.MathUtils.lerp(inf[blinkL], blink, 0.5);
            if (blinkR !== undefined) inf[blinkR] = inf[blinkL];
        }
    });

    return (
        <group {...props} dispose={null}>
            <primitive object={scene} />
        </group>
    );
};

useGLTF.preload("/models/backup_head_with_cloth.glb");
export default Avatar;

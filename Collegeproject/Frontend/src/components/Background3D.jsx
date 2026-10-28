import { Canvas, useFrame } from '@react-three/fiber';
import { useRef, useMemo } from 'react';
import * as THREE from 'three';

function ParticleField({ count = 1500 }) {
    const mesh = useRef();
    const dummy = useMemo(() => new THREE.Object3D(), []);

    // Generate particles for a light, clean atmosphere (soft blue/grey)
    const particles = useMemo(() => {
        const temp = [];
        for (let i = 0; i < count; i++) {
            const x = (Math.random() - 0.5) * 80; // Tighter spread
            const y = (Math.random() - 0.5) * 80;
            const z = (Math.random() - 0.5) * 50;
            const speed = Math.random() * 0.02;
            const factor = Math.random() * 5;
            const scale = Math.random();
            temp.push({ x, y, z, speed, factor, scale });
        }
        return temp;
    }, [count]);

    useFrame((state) => {
        const time = state.clock.getElapsedTime();

        // Smooth mouse look - Unused but kept for potential future use or remove completely if strict
        // const targetX = (state.mouse.x * 5);
        // const targetY = (state.mouse.y * 5);

        particles.forEach((particle, i) => {
            let { x, y, z, factor, scale } = particle;

            // Gentle floating motion
            const newY = y + Math.sin(time * 0.3 + factor) * 1.5;
            const newX = x + Math.cos(time * 0.2 + factor) * 1.5;

            // Mouse parallax
            const parallaxX = newX + (state.mouse.x * z * 0.05);
            const parallaxY = newY + (state.mouse.y * z * 0.05);

            dummy.position.set(parallaxX, parallaxY, z);

            // Breathing scale effect
            const s = scale * (0.5 + Math.sin(time + factor) * 0.2);
            dummy.scale.set(s, s, s);

            dummy.updateMatrix();
            mesh.current.setMatrixAt(i, dummy.matrix);
        });
        mesh.current.instanceMatrix.needsUpdate = true;
    });

    return (
        <>
            <instancedMesh ref={mesh} args={[null, null, count]}>
                <sphereGeometry args={[0.08, 12, 12]} />
                {/* Darker color for visibility on light background */}
                <meshBasicMaterial color="#64748b" transparent opacity={0.4} />
            </instancedMesh>
        </>
    );
}

function FloatingShapes({ count = 20 }) {
    const mesh = useRef();
    const dummy = useMemo(() => new THREE.Object3D(), []);
    const shapes = useMemo(() => {
        const temp = [];
        for (let i = 0; i < count; i++) {
            const x = (Math.random() - 0.5) * 60;
            const y = (Math.random() - 0.5) * 40;
            const z = (Math.random() - 0.5) * 30 - 10;
            temp.push({ x, y, z, speed: Math.random() * 0.1, rotd: Math.random() });
        }
        return temp;
    }, [count]);

    useFrame((state) => {
        const time = state.clock.getElapsedTime();
        shapes.forEach((p, i) => {
            const newY = p.y + Math.sin(time * 0.1 + p.x) * 2;
            dummy.position.set(p.x, newY, p.z);

            dummy.rotation.x = time * p.speed;
            dummy.rotation.y = time * p.speed * 0.5;

            const scale = 1 + Math.sin(time * 0.2 + i) * 0.3;
            dummy.scale.set(scale, scale, scale);

            dummy.updateMatrix();
            mesh.current.setMatrixAt(i, dummy.matrix);
        });
        mesh.current.instanceMatrix.needsUpdate = true;
    });

    return (
        <instancedMesh ref={mesh} args={[null, null, count]}>
            <icosahedronGeometry args={[1, 0]} />
            <meshStandardMaterial color="#6366f1" transparent opacity={0.1} wireframe />
        </instancedMesh>
    );
}


export default function Background3D() {
    return (
        <div style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', zIndex: -1, background: '#f8fafc' }}>
            <Canvas camera={{ fov: 60, position: [0, 0, 30] }}>
                <fog attach="fog" args={['#f8fafc', 20, 60]} />
                <ambientLight intensity={0.8} />
                <pointLight position={[10, 10, 10]} intensity={0.5} color="#6366f1" />

                <ParticleField count={1000} />
                <FloatingShapes count={15} />
            </Canvas>
        </div>
    );
}

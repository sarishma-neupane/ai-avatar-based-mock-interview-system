import { Environment, OrbitControls, Center } from "@react-three/drei";
import Avatar from "./Avatar";

export const Experience = () => {
    return (
        <>
            <OrbitControls
                enablePan={false}
                enableZoom={false}
                enableRotate={false}
                minPolarAngle={Math.PI / 2.2}
                maxPolarAngle={Math.PI / 2.2}
                target={[0, 0.15, 0]}
            />
            <Center>
                <Avatar position={[0, 6.5, 0.001]} />
            </Center>
            <ambientLight intensity={0.8} />
            <directionalLight position={[2, 2, 2]} intensity={1.5} castShadow />
            <Environment preset="sunset" />
        </>
    );
};

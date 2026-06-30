import { Html, Line, Stars } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import gsap from "gsap";
import { useEffect, useMemo, useRef } from "react";
import type { Group, Mesh } from "three";

type CoreProps = {
  status?: string;
  locale: "zh-TW" | "en";
  activeRules: number;
  citations: number;
  tokensAvoided: number;
};

const nodeConfig = [
  { key: "S", labelZh: "主體", labelEn: "Subject", color: "#72a5ff", position: [-2.6, 1.2, 0] as [number, number, number] },
  { key: "C", labelZh: "因果", labelEn: "Causality", color: "#67e8f9", position: [-1.2, -1.65, 0.35] as [number, number, number] },
  { key: "B", labelZh: "邊界", labelEn: "Boundary", color: "#facc15", position: [1.35, -1.65, 0.2] as [number, number, number] },
  { key: "K", labelZh: "依據", labelEn: "Key", color: "#fb7185", position: [2.6, 1.15, -0.1] as [number, number, number] },
  { key: "R", labelZh: "責任", labelEn: "Responsibility", color: "#4ade80", position: [0, 2.15, 0.25] as [number, number, number] },
];

function CoreNode({ node, index, energy }: { node: (typeof nodeConfig)[number]; index: number; energy: number }) {
  const mesh = useRef<Mesh>(null);
  useFrame(({ clock }) => {
    if (!mesh.current) return;
    const pulse = 1 + Math.sin(clock.elapsedTime * 1.8 + index) * 0.055 * energy;
    mesh.current.scale.setScalar(pulse);
    mesh.current.rotation.x += 0.002;
    mesh.current.rotation.y += 0.004;
  });
  return (
    <group position={node.position}>
      <mesh ref={mesh}>
        <icosahedronGeometry args={[0.42, 2]} />
        <meshStandardMaterial color={node.color} emissive={node.color} emissiveIntensity={0.7 + energy * 0.55} roughness={0.2} metalness={0.45} />
      </mesh>
      <mesh scale={1.55}>
        <torusGeometry args={[0.42, 0.018, 12, 64]} />
        <meshBasicMaterial color={node.color} transparent opacity={0.55} />
      </mesh>
      <Html center distanceFactor={8} position={[0, -0.72, 0]}>
        <span className="core-node-label" data-node={node.key}>{node.key}</span>
      </Html>
    </group>
  );
}

function CoreScene({ status }: { status?: string }) {
  const core = useRef<Group>(null);
  const energy = status === "completed" || status === "storage_committed" ? 1.3 : status === "confirmed" || status === "waiting_review" ? 1.05 : 0.72;
  const lines = useMemo(() => nodeConfig.map((node) => [node.position, [0, 0.25, 0] as [number, number, number]]), []);
  useFrame(({ clock }) => {
    if (!core.current) return;
    core.current.rotation.y = Math.sin(clock.elapsedTime * 0.16) * 0.12;
    core.current.rotation.x = Math.cos(clock.elapsedTime * 0.12) * 0.035;
  });
  return (
    <>
      <ambientLight intensity={0.75} />
      <pointLight position={[0, 2, 5]} intensity={35} color="#dbeafe" />
      <pointLight position={[-4, -2, 2]} intensity={18} color="#38bdf8" />
      <Stars radius={34} depth={18} count={900} factor={2.2} saturation={0} fade speed={0.35} />
      <group ref={core}>
        {lines.map((points, index) => <Line key={nodeConfig[index].key} points={points} color={nodeConfig[index].color} lineWidth={1.1} transparent opacity={0.52} />)}
        <mesh position={[0, 0.25, 0]}>
          <sphereGeometry args={[0.72, 48, 48]} />
          <meshPhysicalMaterial color="#dbeafe" emissive="#60a5fa" emissiveIntensity={1.7 * energy} roughness={0.05} metalness={0.38} transmission={0.15} />
        </mesh>
        <mesh position={[0, 0.25, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[1.05, 0.025, 16, 96]} />
          <meshBasicMaterial color="#93c5fd" transparent opacity={0.7} />
        </mesh>
        {nodeConfig.map((node, index) => <CoreNode key={node.key} node={node} index={index} energy={energy} />)}
      </group>
    </>
  );
}

export default function ResponsibilityCore({ status, locale, activeRules, citations, tokensAvoided }: CoreProps) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!panel.current) return;
    const context = gsap.context(() => {
      gsap.fromTo(".core-readout > *", { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, stagger: 0.06, ease: "power2.out" });
    }, panel);
    return () => context.revert();
  }, [status, activeRules, citations]);

  const stage = status === "completed" || status === "storage_committed"
    ? (locale === "en" ? "SEALED" : "已入庫")
    : status === "waiting_review"
      ? (locale === "en" ? "REVIEW" : "待驗收")
      : status === "confirmed"
        ? (locale === "en" ? "SIGNED" : "已簽名")
        : (locale === "en" ? "DRAFT" : "草案");

  return (
    <div className="responsibility-core" ref={panel} data-testid="responsibility-core">
      <Canvas data-testid="scbkr-canvas" camera={{ position: [0, 0.15, 8.2], fov: 47 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }}>
        <CoreScene status={status} />
      </Canvas>
      <div className="core-title">
        <span>SCBKR / RESPONSIBILITY CORE</span>
        <strong>{stage}</strong>
      </div>
      <div className="core-readout" aria-label="SCBKR core status">
        <span><b>{activeRules}</b>{locale === "en" ? " active rules" : " 條啟用規則"}</span>
        <span><b>{citations}</b>{locale === "en" ? " signed citations" : " 筆有效引用"}</span>
        <span><b>{tokensAvoided}</b>{locale === "en" ? " tokens avoided" : " 估算節省 Token"}</span>
        <span className="live-signal"><i />{locale === "en" ? "local runtime" : "本機運行"}</span>
      </div>
    </div>
  );
}

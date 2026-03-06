import { useState } from "react";
import { useInView } from "../hooks/useInView";
import { motion, AnimatePresence } from "motion/react";

const steps = [
    {
        id: 1,
        label: "Step 1",
        title: "Collect",
        desc: "Deploy lightweight agents to collect infrastructure metrics from your Kubernetes clusters, VMs, or cloud services. Agents send CPU, memory, network, and custom metrics to the PreScale inference engine.",
        code: `# Install the PreScale agent
pip install prescale-agent

# Configure metrics collection
prescale agent start \\
  --api-url http://prescale:8001 \\
  --interval 30s \\
  --metrics cpu,memory,network,disk`,
    },
    {
        id: 2,
        label: "Step 2",
        title: "Predict",
        desc: "ML models forecast resource utilization 30 minutes ahead using Prophet and XGBoost. The engine automatically detects anomalies, classifies severity, and tracks model accuracy across 108 engineered features.",
        code: `# Forecast endpoint
curl -X POST /v1/predict \\
  -d '{"metric": "cpu_usage", "horizon": 30}'

# Response
{
  "predictions": [
    {"timestamp": "2025-03-05T16:00:00Z",
     "value": 78.2, "confidence": 0.92}
  ],
  "model_accuracy": {"mape": 2.6}
}`,
    },
    {
        id: 3,
        label: "Step 3",
        title: "Scale",
        desc: "Get confidence-scored scaling recommendations in real-time. PreScale recommends proactive scaling actions before traffic spikes hit, integrating with K8s HPA, AWS Auto Scaling, and cloud-native tooling.",
        code: `# Scaling recommendation
curl /v1/recommend

# Response
{
  "action": "scale_out",
  "current_replicas": 3,
  "recommended_replicas": 5,
  "confidence": 0.87,
  "reason": "Predicted utilization exceeds
    80% threshold in 12 minutes"
}`,
    },
];

export function HowItWorks() {
    const [active, setActive] = useState(0);
    const [ref, isInView] = useInView({ threshold: 0.1 });

    const step = steps[active];

    return (
        <section ref={ref} className="py-24">
            <div className="max-w-6xl mx-auto px-6">
                <motion.div
                    className="text-center mb-16"
                    initial={{ opacity: 0, y: 16 }}
                    animate={isInView ? { opacity: 1, y: 0 } : {}}
                    transition={{ duration: 0.5 }}
                >
                    <span className="section-badge">
                        <span>🔄</span> Process
                    </span>
                    <h2 className="mt-6 text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                        Our Simple & <span className="accent-serif">Smart Process</span>
                    </h2>
                    <p className="mt-4 text-base sm:text-lg max-w-xl mx-auto" style={{ color: 'var(--text-secondary)' }}>
                        From metrics collection to proactive scaling, all in three steps.
                    </p>
                </motion.div>

                {/* Main card */}
                <motion.div
                    className="gradient-card"
                    initial={{ opacity: 0, y: 24 }}
                    animate={isInView ? { opacity: 1, y: 0 } : {}}
                    transition={{ delay: 0.2, duration: 0.5 }}
                >
                    {/* Tabs */}
                    <div className="flex border-b" style={{ borderColor: 'var(--border)' }}>
                        {steps.map((s, i) => (
                            <button
                                key={s.id}
                                onClick={() => setActive(i)}
                                className="flex-1 py-4 px-4 text-sm font-semibold text-center transition-all cursor-pointer relative"
                                style={{
                                    color: active === i ? 'var(--accent)' : 'var(--text-muted)',
                                    background: active === i ? 'var(--accent-light)' : 'transparent',
                                }}
                            >
                                {s.label}: {s.title}
                                {active === i && (
                                    <motion.div
                                        className="absolute bottom-0 left-0 right-0 h-[2px]"
                                        style={{ background: 'var(--accent-gradient)' }}
                                        layoutId="processTab"
                                    />
                                )}
                            </button>
                        ))}
                    </div>

                    {/* Content */}
                    <div className="grid grid-cols-1 lg:grid-cols-2 min-h-[380px]">
                        {/* Code panel */}
                        <div className="relative">
                            <div className="code-window rounded-none h-full" style={{ borderRadius: 0 }}>
                                <div className="title-bar">
                                    <div className="flex gap-2">
                                        <div className="dot" style={{ background: '#ff5f57' }} />
                                        <div className="dot" style={{ background: '#ffbd2e' }} />
                                        <div className="dot" style={{ background: '#28c840' }} />
                                    </div>
                                    <span className="ml-3 text-[11px] font-mono" style={{ color: 'rgba(255,255,255,0.3)' }}>
                                        terminal — bash
                                    </span>
                                </div>
                                <div className="p-5">
                                    <AnimatePresence mode="wait">
                                        <motion.pre
                                            key={step.id}
                                            className="text-[13px] font-mono leading-relaxed whitespace-pre-wrap"
                                            style={{ color: 'rgba(255,255,255,0.7)' }}
                                            initial={{ opacity: 0, x: -16 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            exit={{ opacity: 0, x: 16 }}
                                            transition={{ duration: 0.25 }}
                                        >
                                            <code>{step.code}</code>
                                        </motion.pre>
                                    </AnimatePresence>
                                </div>
                            </div>
                        </div>

                        {/* Description panel */}
                        <div className="p-8 lg:p-10 flex flex-col justify-center">
                            <AnimatePresence mode="wait">
                                <motion.div
                                    key={step.id}
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    exit={{ opacity: 0, x: -20 }}
                                    transition={{ duration: 0.25 }}
                                >
                                    <div className="text-xs font-mono font-bold mb-3 tracking-wider uppercase" style={{ color: 'var(--accent)' }}>
                                        Step 0{step.id}
                                    </div>
                                    <h3 className="text-2xl sm:text-3xl font-extrabold mb-4" style={{ color: 'var(--text-primary)' }}>
                                        {step.title}
                                    </h3>
                                    <p className="text-base leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
                                        {step.desc}
                                    </p>
                                </motion.div>
                            </AnimatePresence>
                        </div>
                    </div>
                </motion.div>
            </div>
        </section>
    );
}

interface MiniChartProps {
    points?: number[]
    color?: string
}

export function MiniChart({ points = [32, 28, 35, 42, 38, 55, 62, 58, 72, 68, 78, 82], color = 'rgb(129,140,248)' }: MiniChartProps) {
    const max = Math.max(...points)
    const min = Math.min(...points)
    const width = 280
    const height = 80
    const pad = 4

    const pathData = points
        .map((p, i) => {
            const x = pad + (i / (points.length - 1)) * (width - pad * 2)
            const y = height - pad - ((p - min) / (max - min)) * (height - pad * 2)
            return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
        })
        .join(' ')

    const areaPath = `${pathData} L ${width - pad} ${height} L ${pad} ${height} Z`

    return (
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-20">
            <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity="0.3" />
                    <stop offset="100%" stopColor={color} stopOpacity="0" />
                </linearGradient>
            </defs>
            <path d={areaPath} fill="url(#chartGrad)" />
            <path d={pathData} fill="none" stroke={color} strokeWidth="2" />
        </svg>
    )
}

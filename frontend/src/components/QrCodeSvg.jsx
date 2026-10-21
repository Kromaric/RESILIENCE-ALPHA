/**
 * Geometric SVG QR Code component (200x200 px).
 * Clean, crisp vector rendering with corner positional finder patterns.
 * No emojis used.
 */
export default function QrCodeSvg({ size = 200, className = '' }) {
  // 21x21 standard QR grid matrix representation for Orbe
  const grid = [
    [1,1,1,1,1,1,1,0,1,0,1,1,0,0,1,1,1,1,1,1,1],
    [1,0,0,0,0,0,1,0,0,1,0,1,1,0,1,0,0,0,0,0,1],
    [1,0,1,1,1,0,1,0,1,0,1,0,0,0,1,0,1,1,1,0,1],
    [1,0,1,1,1,0,1,0,0,1,1,1,0,0,1,0,1,1,1,0,1],
    [1,0,1,1,1,0,1,0,1,1,0,0,1,0,1,0,1,1,1,0,1],
    [1,0,0,0,0,0,1,0,0,0,1,1,0,0,1,0,0,0,0,0,1],
    [1,1,1,1,1,1,1,0,1,0,1,0,1,0,1,1,1,1,1,1,1],
    [0,0,0,0,0,0,0,0,1,1,0,1,0,0,0,0,0,0,0,0,0],
    [1,1,0,1,0,1,1,1,0,0,1,0,1,1,0,1,0,1,1,0,1],
    [0,1,1,0,1,0,0,1,1,0,0,1,0,1,1,0,1,0,0,1,0],
    [1,0,1,1,0,1,0,0,1,1,1,0,1,0,0,1,1,0,1,1,1],
    [0,1,0,1,1,0,1,1,0,1,0,1,1,0,1,0,0,1,0,1,0],
    [1,1,1,0,0,1,0,1,1,0,1,0,0,1,0,1,1,1,0,0,1],
    [0,0,0,0,0,0,0,0,1,0,1,1,0,1,0,1,0,0,1,1,0],
    [1,1,1,1,1,1,1,0,1,1,0,0,1,0,1,0,1,0,1,0,1],
    [1,0,0,0,0,0,1,0,0,1,1,1,0,1,0,0,1,1,0,1,0],
    [1,0,1,1,1,0,1,0,1,0,0,1,1,0,1,1,0,1,1,0,1],
    [1,0,1,1,1,0,1,0,0,1,0,0,1,1,0,1,0,0,1,1,1],
    [1,0,1,1,1,0,1,0,1,1,1,0,0,1,1,0,1,1,0,0,0],
    [1,0,0,0,0,0,1,0,1,0,1,1,0,0,1,0,0,1,1,0,1],
    [1,1,1,1,1,1,1,0,0,1,0,1,1,0,1,1,0,1,0,1,1],
  ];

  const moduleSize = size / 25; // with quiet zone margin of 2 modules on each side

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={`select-none ${className}`}
      aria-label="Code QR de paiement Orbe"
    >
      {/* Background */}
      <rect width={size} height={size} fill="#ffffff" rx="12" />

      {/* QR Code Matrix */}
      <g transform={`translate(${moduleSize * 2}, ${moduleSize * 2})`}>
        {grid.map((row, rIdx) =>
          row.map((cell, cIdx) => {
            if (cell !== 1) return null;
            return (
              <rect
                key={`${rIdx}-${cIdx}`}
                x={cIdx * moduleSize}
                y={rIdx * moduleSize}
                width={moduleSize}
                height={moduleSize}
                fill="#0f1a1d"
              />
            );
          })
        )}
      </g>
    </svg>
  );
}

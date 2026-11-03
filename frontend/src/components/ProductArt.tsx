export function ProductArt({
  vector,
  small = false,
}: {
  vector: string;
  small?: boolean;
}) {
  return (
    <div
      className={`product-art ${vector} ${small ? "small-art" : ""}`}
      aria-hidden="true"
    >
      <div className="art-orbit one" />
      <div className="art-orbit two" />
      <span className="art-star">✳</span>
      {vector === "batch" ? (
        <svg viewBox="0 0 260 150">
          <ellipse
            cx="133"
            cy="133"
            rx="65"
            ry="8"
            fill="#bca7b8"
            opacity=".3"
          />
          <g transform="rotate(-9 124 80)">
            <path d="M82 20h85l9 109H73z" fill="#44283d" />
            <path d="M82 20h85v12H82z" fill="#65455d" />
            <rect x="84" y="50" width="79" height="60" rx="2" fill="#f56f45" />
            <text
              x="123"
              y="66"
              textAnchor="middle"
              fill="#402331"
              fontSize="7"
              fontWeight="700"
            >
              MASALACLUB
            </text>
            <text
              x="123"
              y="84"
              textAnchor="middle"
              fill="#fff6dd"
              fontSize="15"
              fontWeight="700"
            >
              everyday
            </text>
            <text
              x="123"
              y="99"
              textAnchor="middle"
              fill="#fff6dd"
              fontSize="13"
              fontWeight="700"
            >
              MASALA
            </text>
            <circle cx="123" cy="118" r="3" fill="#f8e0b3" />
          </g>
          <path d="M179 103l11-12 8 19-18 3z" fill="#d67144" />
          <circle cx="65" cy="117" r="5" fill="#e9ad62" />
          <circle cx="188" cy="124" r="4" fill="#bc5a47" />
        </svg>
      ) : vector === "counterfeit" ? (
        <svg viewBox="0 0 260 150">
          <ellipse
            cx="131"
            cy="133"
            rx="70"
            ry="8"
            fill="#9591c8"
            opacity=".25"
          />
          <g transform="rotate(-7 111 80)">
            <rect x="69" y="35" width="83" height="93" rx="14" fill="#f9f7f0" />
            <rect x="67" y="26" width="87" height="21" rx="7" fill="#574c89" />
            <path d="M70 64h81v44H70z" fill="#7e6fbb" />
            <text
              x="110"
              y="78"
              textAnchor="middle"
              fill="#fff"
              fontSize="8"
              fontWeight="700"
            >
              PEAKFUEL
            </text>
            <text
              x="110"
              y="98"
              textAnchor="middle"
              fill="#fff"
              fontSize="21"
              fontWeight="700"
            >
              WHEY
            </text>
            <rect x="93" y="114" width="34" height="3" rx="1" fill="#d2cbe6" />
          </g>
          <g transform="rotate(9 173 105)">
            <rect x="155" y="82" width="43" height="48" rx="8" fill="#e9a64b" />
            <rect x="153" y="76" width="47" height="12" rx="3" fill="#3c3554" />
            <rect x="160" y="98" width="33" height="21" rx="2" fill="#fff1d7" />
            <text
              x="176"
              y="112"
              textAnchor="middle"
              fill="#a16c2c"
              fontSize="7"
              fontWeight="700"
            >
              HONEY
            </text>
          </g>
        </svg>
      ) : (
        <svg viewBox="0 0 260 150">
          <ellipse
            cx="130"
            cy="133"
            rx="65"
            ry="8"
            fill="#5baf9e"
            opacity=".2"
          />
          <g transform="rotate(-8 116 80)">
            <path d="M84 43l25-18 33 12 15 91H81z" fill="#fffef6" />
            <path d="M109 25l33 12 9 24-42-13z" fill="#9bc8ae" />
            <path d="M84 43l25-18v23L82 66z" fill="#d3e8d8" />
            <path d="M82 66h69l4 46H82z" fill="#3e927d" />
            <text
              x="118"
              y="83"
              textAnchor="middle"
              fill="#e3f6da"
              fontSize="7"
              fontWeight="700"
            >
              DAILYDROP
            </text>
            <text
              x="118"
              y="104"
              textAnchor="middle"
              fill="#fff"
              fontSize="21"
              fontWeight="700"
            >
              MILK
            </text>
            <circle cx="123" cy="34" r="6" fill="#fffdf6" />
          </g>
          <path d="M170 101q18-17 24 3l-13 26-16-10z" fill="#6eaf51" />
          <path
            d="M176 102q-5-17 8-22"
            fill="none"
            stroke="#46865d"
            strokeWidth="4"
          />
        </svg>
      )}
    </div>
  );
}

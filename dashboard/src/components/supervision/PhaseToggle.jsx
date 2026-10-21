const options = [
  ['avant', 'Avant'],
  ['pendant', 'Pendant'],
  ['apres', 'Après'],
]

export default function PhaseToggle({ value, onChange }) {
  return (
    <div className="inline-flex rounded-md border border-line bg-bg p-1">
      {options.map(([key, label]) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`rounded px-3 py-1.5 text-xs transition ${
            value === key ? 'bg-accent text-bg font-medium' : 'text-gray-300 hover:text-white'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
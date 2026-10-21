export default function Card({ className = '', children }) {
  return (
    <div className={`rounded-lg border border-line bg-surface p-4 ${className}`}>
      {children}
    </div>
  )
}
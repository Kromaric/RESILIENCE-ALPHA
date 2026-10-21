// Distingue les blocs alimentés par bo-api de ceux qui affichent encore des données fictives
export default function LiveTag() {
  return (
    <span
      title="Donnée réelle, lue par bo-api"
      className="rounded border border-accent/40 px-1 font-mono text-[10px] font-normal text-accent"
    >
      réel
    </span>
  )
}

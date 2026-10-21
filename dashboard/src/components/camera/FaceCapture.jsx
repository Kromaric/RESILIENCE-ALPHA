import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, CameraOff, Loader2, ScanFace } from 'lucide-react'

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// Caméra USB du PC Hôte (getUserMedia). L'aperçu est affiché en miroir, comme un miroir :
// tourner la tête vers sa gauche déplace le visage vers la gauche de l'écran. Les images
// envoyées ne le sont pas (le serveur mesure la rotation sur l'image réelle).
function useCamera(active) {
  const videoRef = useRef(null)
  const [status, setStatus] = useState('starting') // starting | on | error (off : dérivé)
  const [error, setError] = useState(null)

  // Sans HTTPS (hors localhost), le navigateur ne donne pas accès à la caméra
  const supported = Boolean(navigator.mediaDevices?.getUserMedia)

  useEffect(() => {
    if (!active || !supported) return
    let stream
    let cancelled = false
    navigator.mediaDevices
      .getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false })
      .then((s) => {
        if (cancelled) {
          s.getTracks().forEach((t) => t.stop())
          return
        }
        stream = s
        if (videoRef.current) videoRef.current.srcObject = s
        setStatus('on')
      })
      .catch((err) => {
        if (cancelled) return
        setStatus('error')
        setError(
          err?.name === 'NotAllowedError'
            ? "Accès à la caméra refusé : autorisez-le dans le navigateur."
            : 'Caméra USB introuvable ou déjà utilisée.',
        )
      })
    // La caméra s'éteint dès que le composant n'en a plus besoin
    return () => {
      cancelled = true
      stream?.getTracks().forEach((t) => t.stop())
      setStatus('starting') // prochaine activation : « Activation de la caméra… »
      setError(null)
    }
  }, [active, supported])

  // États dérivés (caméra éteinte, non prise en charge) : pas de setState dans l'effet
  if (!active) return { videoRef, status: 'off', error: null }
  if (!supported) {
    return {
      videoRef,
      status: 'error',
      error: 'Caméra non disponible : ouvrez le dashboard en HTTPS ou sur localhost.',
    }
  }
  return { videoRef, status, error }
}

function grab(video, canvas) {
  if (!video?.videoWidth) return null
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0)
  return canvas.toDataURL('image/jpeg', 0.85).split(',')[1]
}

/**
 * Capture de visage pour bo-api.
 *  - mode « turn » (connexion) : tourner la tête vers `direction` après un compte à rebours ;
 *  - mode « sweep » (enregistrement) : tourner lentement la tête de gauche à droite.
 * `onFrames(frames)` reçoit les images JPEG en base64 ; `busy` désactive le bouton pendant l'envoi.
 */
export default function FaceCapture({
  active = true,
  mode = 'turn',
  direction = 'left',
  frames = 12,
  intervalMs = 300,
  busy = false,
  actionLabel = 'Valider mon visage',
  onFrames,
}) {
  const { videoRef, status, error } = useCamera(active)
  const canvasRef = useRef(null)
  const [countdown, setCountdown] = useState(0)
  const [captured, setCaptured] = useState(null) // null : pas de capture en cours

  const directionLabel = direction === 'left' ? 'gauche' : 'droite'
  const Arrow = direction === 'left' ? ArrowLeft : ArrowRight
  const instruction =
    mode === 'sweep'
      ? 'Tournez lentement la tête de gauche à droite'
      : `Tournez la tête vers la ${directionLabel}`

  const capture = useCallback(async () => {
    for (let n = 3; n > 0; n--) {
      setCountdown(n)
      await sleep(700)
    }
    setCountdown(0)
    const images = []
    for (let i = 0; i < frames; i++) {
      const image = grab(videoRef.current, canvasRef.current)
      if (image) images.push(image)
      setCaptured(i + 1)
      if (i < frames - 1) await sleep(intervalMs)
    }
    setCaptured(null)
    onFrames(images)
  }, [frames, intervalMs, onFrames, videoRef])

  const capturing = countdown > 0 || captured !== null

  return (
    <div className="flex flex-col items-center">
      <div className="relative aspect-[4/3] w-full max-w-sm overflow-hidden rounded-lg border border-line bg-black">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={`h-full w-full -scale-x-100 object-cover ${status === 'on' ? '' : 'invisible'}`}
        />
        <canvas ref={canvasRef} className="hidden" />

        {status !== 'on' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center text-xs text-muted">
            {status === 'error' ? (
              <>
                <CameraOff size={28} className="text-danger" />
                <span className="text-gray-200">{error}</span>
              </>
            ) : status === 'off' ? (
              <>
                <CameraOff size={28} />
                Caméra éteinte
              </>
            ) : (
              <>
                <Loader2 size={24} className="animate-spin text-accent" />
                Activation de la caméra USB…
              </>
            )}
          </div>
        )}

        {status === 'on' && countdown > 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/45 text-gray-100">
            <span className="text-5xl font-semibold tabular-nums">{countdown}</span>
            <span className="mt-1 text-xs">Regardez la caméra, de face</span>
          </div>
        )}

        {status === 'on' && captured !== null && (
          <div className="absolute inset-x-0 bottom-0 flex flex-col items-center gap-1.5 bg-gradient-to-t from-black/80 to-transparent p-3">
            <span
              className={`flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-sm font-semibold text-bg ${
                mode === 'turn' && direction === 'right' ? 'flex-row-reverse' : ''
              }`}
            >
              {mode === 'turn' && <Arrow size={16} className="animate-pulse" />}
              {instruction}
            </span>
            <span className="font-mono text-[11px] text-gray-300">
              Capture {captured}/{frames}
            </span>
          </div>
        )}
      </div>

      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted">
        <ScanFace size={14} className="text-accent" />
        Consigne : <span className="font-medium text-gray-200">{instruction}</span>
        {mode === 'turn' && ', puis revenez de face.'}
      </p>

      <button
        type="button"
        onClick={capture}
        disabled={status !== 'on' || capturing || busy}
        className="mt-4 flex w-full max-w-sm items-center justify-center gap-2 rounded-md bg-accent py-2 text-sm font-medium text-bg hover:brightness-110 disabled:opacity-50"
      >
        {(capturing || busy) && <Loader2 size={14} className="animate-spin" />}
        {busy ? 'Vérification…' : capturing ? 'Capture en cours…' : actionLabel}
      </button>
    </div>
  )
}

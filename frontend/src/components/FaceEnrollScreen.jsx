import { useState, useEffect, useRef, useCallback } from 'react';
import { ArrowLeft, ScanFace, CheckCircle2, AlertCircle, ShieldCheck, RefreshCw, CameraOff, Loader2 } from 'lucide-react';
import { useApp } from '../context/useApp';
import { enrollFace } from '../services/api';

/**
 * Screen: Biometric Facial Enrollment (RGPD Art. 9).
 * Allows the user to register their face with explicit consent.
 * Strictly requires an active camera stream with live frames.
 * No emojis used.
 */
export default function FaceEnrollScreen() {
  const { authToken, setCurrentScreen, syncBackendData } = useApp();

  const [consentChecked, setConsentChecked] = useState(false);
  const [enrollState, setEnrollState] = useState('IDLE'); // 'IDLE', 'CAPTURING', 'ENROLLED', 'ERROR'
  const [capturedCount, setCapturedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  // Camera state: 'CHECKING' | 'ACTIVE' | 'ERROR'
  const [cameraStatus, setCameraStatus] = useState('CHECKING');
  const [cameraError, setCameraError] = useState('');
  const [cameraRetry, setCameraRetry] = useState(0);

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const isEnrollingRef = useRef(false);
  const isMountedRef = useRef(true);

  const totalFrames = 16;
  const intervalMs = 250;

  // Single frame capture as base64 JPEG without prefix
  const captureCurrentFrameB64 = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return null;
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (video.videoWidth === 0 || video.videoHeight === 0) return null;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    const commaIndex = dataUrl.indexOf(',');
    return commaIndex !== -1 ? dataUrl.slice(commaIndex + 1) : dataUrl;
  }, []);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const retryCamera = () => {
    setCameraStatus('CHECKING');
    setCameraError('');
    setCameraRetry((c) => c + 1);
  };

  useEffect(() => {
    isMountedRef.current = true;
    let streamInstance = null;

    async function startCamera() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        if (!isMountedRef.current) return;
        setCameraStatus('ERROR');
        setCameraError("Votre navigateur ne supporte pas l'accès à la caméra.");
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 640 },
          },
        });

        if (!isMountedRef.current) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamInstance = stream;
        streamRef.current = stream;

        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.onloadedmetadata = () => {
            videoRef.current?.play().then(() => {
              const track = stream.getVideoTracks()[0];
              if (track && track.readyState === 'live' && videoRef.current.videoWidth > 0) {
                setCameraStatus('ACTIVE');
              } else {
                setCameraStatus('ERROR');
                setCameraError('Le flux vidéo de la caméra est indisponible.');
              }
            }).catch((playErr) => {
              setCameraStatus('ERROR');
              setCameraError('Impossible de démarrer la vidéo : ' + playErr.message);
            });
          };
        }
      } catch (err) {
        console.warn('Webcam initialization failed in FaceEnroll:', err);
        if (!isMountedRef.current) return;
        setCameraStatus('ERROR');
        if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
          setCameraError("Accès à la caméra refusé. Veuillez autoriser l'accès dans les paramètres de votre navigateur.");
        } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
          setCameraError('Aucune caméra détectée sur votre appareil.');
        } else {
          setCameraError("Erreur d'accès à la caméra : " + (err.message || 'Périphérique indisponible.'));
        }
      }
    }

    startCamera();

    return () => {
      isMountedRef.current = false;
      if (streamInstance) {
        streamInstance.getTracks().forEach((track) => track.stop());
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
    };
  }, [cameraRetry]);

  // Perform multi-frame enrollment capture
  const startEnrollment = useCallback(async () => {
    if (cameraStatus !== 'ACTIVE') {
      setErrorMessage('La caméra doit être active pour capturer votre visage.');
      return;
    }
    if (!consentChecked) {
      setErrorMessage('Veuillez cocher la case de consentement RGPD pour continuer.');
      return;
    }
    if (isEnrollingRef.current) return;
    isEnrollingRef.current = true;
    setEnrollState('CAPTURING');
    setErrorMessage('');
    setCapturedCount(0);

    try {
      const frames = [];

      for (let i = 0; i < totalFrames; i++) {
        const frameB64 = captureCurrentFrameB64();
        if (frameB64) {
          frames.push(frameB64);
        }
        setCapturedCount(i + 1);
        if (i < totalFrames - 1) {
          await sleep(intervalMs);
        }
      }

      if (frames.length < 6) {
        throw new Error('Capture insuffisante : assurez-vous que votre caméra diffuse une image nette.');
      }

      // Call backend enrollment endpoint with real camera frames
      if (authToken) {
        await enrollFace(frames, authToken);
      } else {
        throw new Error('Session non authentifiée. Veuillez vous reconnecter.');
      }

      setEnrollState('ENROLLED');
      await sleep(1000);

      if (authToken) {
        await syncBackendData(authToken);
      }
      setCurrentScreen('HOME');
    } catch (err) {
      setEnrollState('ERROR');
      setErrorMessage(err.message || "Échec de l'enregistrement. Vérifiez votre éclairage et réessayez.");
    } finally {
      isEnrollingRef.current = false;
    }
  }, [cameraStatus, consentChecked, captureCurrentFrameB64, authToken, syncBackendData, setCurrentScreen]);

  const handleSkip = () => {
    setCurrentScreen('HOME');
  };

  return (
    <div className="flex-1 flex flex-col justify-between overflow-y-auto no-scrollbar pb-5 select-none">
      {/* Top Header */}
      <div>
        <div className="px-5 pt-4 pb-2 flex items-center justify-between">
          <button
            type="button"
            onClick={handleSkip}
            className="p-1 -ml-1 text-[#0f1a1d] hover:text-[#0e5a6b] rounded-lg transition-colors cursor-pointer"
            aria-label="Passer"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>

          <span className="bg-[#dcecef] text-[#0a4552] rounded-full px-2.5 py-0.5 text-xs font-semibold inline-flex items-center gap-1 shadow-2xs">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Enrôlement biométrique</span>
          </span>
        </div>

        {/* Title & Instructions */}
        <div className="px-6 pt-2 text-center flex flex-col items-center">
          <h2 className="text-[20px] font-semibold text-[#0f1a1d] tracking-tight">
            Activer la reconnaissance faciale
          </h2>
          <p className="text-xs text-[#55636a] max-w-[300px] mt-1 leading-relaxed">
            Sécurisez vos connexions et paiements avec votre visage. Vos photos brutes ne sont jamais conservées.
          </p>
        </div>

        {/* Central Camera Viewport */}
        <div className="mt-4 mb-2 flex flex-col items-center">
          <div
            className={`w-52 h-52 rounded-full overflow-hidden border-4 relative mx-auto flex items-center justify-center transition-colors duration-300 shadow-md ${
              enrollState === 'ENROLLED'
                ? 'border-[#1e7a45] shadow-[0_0_24px_rgba(30,122,69,0.35)]'
                : enrollState === 'ERROR' || cameraStatus === 'ERROR'
                ? 'border-[#c81e1e] shadow-[0_0_24px_rgba(200,30,30,0.35)]'
                : enrollState === 'CAPTURING'
                ? 'border-[#0e5a6b] shadow-[0_0_20px_rgba(14,90,107,0.25)]'
                : cameraStatus === 'ACTIVE'
                ? 'border-[#0e5a6b]'
                : 'border-[#d5dcdf]'
            }`}
          >
            {/* Live Camera Video */}
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className={`w-full h-full object-cover scale-x-[-1] ${
                cameraStatus === 'ACTIVE' ? 'block' : 'hidden'
              }`}
            />

            {/* Camera Checking / Initializing placeholder */}
            {cameraStatus === 'CHECKING' && (
              <div className="w-full h-full bg-[#f0f4f6] flex flex-col items-center justify-center text-[#55636a] p-4 text-center">
                <Loader2 className="w-10 h-10 animate-spin text-[#0e5a6b] mb-2" />
                <span className="text-xs font-medium">Activation de la caméra...</span>
              </div>
            )}

            {/* Camera Error / Inactive placeholder */}
            {cameraStatus === 'ERROR' && (
              <div className="w-full h-full bg-[#ffdad6]/40 flex flex-col items-center justify-center text-[#93000a] p-4 text-center">
                <CameraOff className="w-12 h-12 stroke-[1.5] text-[#ba1a1a] mb-1" />
                <span className="text-xs font-semibold">Caméra inactive</span>
              </div>
            )}

            <canvas ref={canvasRef} className="hidden" />

            {/* Target Reticles (active only when camera is live) */}
            {cameraStatus === 'ACTIVE' && (
              <svg
                className="absolute inset-0 w-full h-full pointer-events-none p-5"
                viewBox="0 0 100 100"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M 20 30 L 20 20 L 30 20 M 70 20 L 80 20 L 80 30 M 80 70 L 80 80 L 70 80 M 30 80 L 20 80 L 20 70"
                  stroke={
                    enrollState === 'ENROLLED'
                      ? '#1e7a45'
                      : enrollState === 'ERROR'
                      ? '#c81e1e'
                      : '#0e5a6b'
                  }
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  opacity={enrollState === 'IDLE' ? 0.6 : 0.9}
                />
              </svg>
            )}

            {/* Laser scanning line during capture */}
            {enrollState === 'CAPTURING' && (
              <div className="absolute left-6 right-6 h-[2px] bg-[#0e5a6b] shadow-[0_0_8px_#0e5a6b] animate-scanline pointer-events-none" />
            )}

            {/* Success Overlay */}
            {enrollState === 'ENROLLED' && (
              <div className="absolute inset-0 bg-[#1e7a45]/20 flex items-center justify-center backdrop-blur-[1px] animate-fadeIn">
                <CheckCircle2 className="w-16 h-16 text-[#1e7a45] fill-white stroke-[2.5]" />
              </div>
            )}

            {/* Error Overlay */}
            {enrollState === 'ERROR' && (
              <div className="absolute inset-0 bg-[#3d1714]/40 flex items-center justify-center backdrop-blur-[1px] animate-fadeIn">
                <AlertCircle className="w-16 h-16 text-[#f47066] stroke-[2.5]" />
              </div>
            )}
          </div>

          {/* Status and Progress Indicator */}
          <div className="mt-3 px-6 text-center min-h-[36px] flex flex-col items-center justify-center">
            {cameraStatus === 'ERROR' && (
              <div className="flex flex-col items-center gap-1.5 max-w-[320px]">
                <div className="bg-[#ffdad6] text-[#93000a] text-xs p-2.5 rounded-xl flex items-start gap-2 shadow-xs text-left">
                  <AlertCircle className="w-4 h-4 mt-0.5 shrink-0 text-[#ba1a1a]" />
                  <span>{cameraError || 'La caméra doit être activée pour enregistrer votre visage.'}</span>
                </div>
                <button
                  type="button"
                  onClick={retryCamera}
                  className="text-xs text-[#0e5a6b] font-medium hover:underline cursor-pointer inline-flex items-center gap-1 mt-0.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  <span>Réessayer d&apos;activer la caméra</span>
                </button>
              </div>
            )}

            {cameraStatus === 'ACTIVE' && enrollState === 'IDLE' && (
              <p className="text-[12px] text-[#55636a] max-w-[280px]">
                Caméra active. Tournez lentement la tête de gauche à droite pendant la capture.
              </p>
            )}

            {enrollState === 'CAPTURING' && (
              <div className="flex flex-col items-center gap-1">
                <span className="font-mono text-xs text-[#0e5a6b] font-semibold animate-pulse inline-flex items-center gap-1.5">
                  <span aria-hidden="true">●</span> Enregistrement ({capturedCount}/{totalFrames})...
                </span>
                <div className="w-36 h-1.5 bg-[#d5dcdf] rounded-full overflow-hidden mt-0.5">
                  <div
                    className="h-full bg-[#0e5a6b] transition-all duration-150 rounded-full"
                    style={{ width: `${(capturedCount / totalFrames) * 100}%` }}
                  />
                </div>
              </div>
            )}

            {enrollState === 'ENROLLED' && (
              <span className="text-[#1e7a45] font-semibold text-xs inline-flex items-center gap-1.5 bg-[#def2e5] px-3 py-1 rounded-full shadow-2xs">
                <CheckCircle2 className="w-4 h-4 stroke-[2.5]" />
                <span>Visage enregistré avec succès</span>
              </span>
            )}

            {enrollState === 'ERROR' && (
              <div className="flex flex-col items-center gap-1">
                <span className="text-[#c81e1e] font-semibold text-xs bg-[#fde8e8] px-3 py-1 rounded-lg border border-[#f8b4b4] max-w-[320px]">
                  {errorMessage}
                </span>
                <button
                  type="button"
                  onClick={startEnrollment}
                  className="text-xs text-[#0e5a6b] font-medium hover:underline mt-1 cursor-pointer inline-flex items-center gap-1"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Réessayer</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* GDPR Explicit Consent Box (Art. 9) */}
        <div className="px-6 mt-1">
          <label className="flex items-start gap-2.5 p-3 rounded-xl bg-white border border-[#d5dcdf] cursor-pointer hover:border-[#7f8c93] transition-colors shadow-2xs">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(e) => {
                setConsentChecked(e.target.checked);
                if (errorMessage) setErrorMessage('');
              }}
              disabled={enrollState === 'CAPTURING'}
              className="mt-0.5 w-4 h-4 rounded text-[#0e5a6b] focus:ring-[#0e5a6b] cursor-pointer"
            />
            <span className="text-[11px] text-[#55636a] leading-tight">
              J&apos;accepte le traitement de mes données biométriques (RGPD art. 9). Seul un gabarit chiffré
              (AES-256) est conservé, aucune photo n&apos;est stockée.
            </span>
          </label>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="px-6 flex flex-col gap-2 pt-2">
        <button
          type="button"
          onClick={startEnrollment}
          disabled={cameraStatus !== 'ACTIVE' || !consentChecked || enrollState === 'CAPTURING' || enrollState === 'ENROLLED'}
          className="w-full h-11 rounded-xl bg-[#0e5a6b] hover:bg-[#0a4552] text-white font-semibold text-xs flex items-center justify-center gap-2 transition-colors cursor-pointer shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <ScanFace className="w-4 h-4" />
          <span>
            {cameraStatus === 'CHECKING'
              ? 'Activation de la caméra...'
              : cameraStatus === 'ERROR'
              ? 'Caméra requise pour enrôlement'
              : enrollState === 'CAPTURING'
              ? 'Capture en cours...'
              : "Démarrer l'enregistrement biométrique"}
          </span>
        </button>

        <button
          type="button"
          onClick={handleSkip}
          disabled={enrollState === 'CAPTURING'}
          className="text-xs text-[#55636a] hover:text-[#0f1a1d] py-1 text-center font-medium cursor-pointer"
        >
          Configurer plus tard
        </button>
      </div>
    </div>
  );
}

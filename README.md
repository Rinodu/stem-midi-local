# Stem / MIDI Local

Frontend: **https://rinodu.github.io/stem-midi-local/**. Backend: PC Windows milik pengguna, di `127.0.0.1:8765`. Satu repo berisi keduanya; GitHub Pages tidak menjalankan AI.

Upload audio → uji cuplikan → pisahkan stem → dengarkan/download WAV → pilih stem bernada → buat/download MIDI, CSV not dan ZIP. Piano roll tersedia untuk pemeriksaan visual, bukan editor. Riwayat hasil disimpan lokal.

## Mulai di Windows

1. Download ZIP repo lewat **Code → Download ZIP**, lalu ekstrak ke folder yang bisa ditulis. Atau `git clone https://github.com/Rinodu/stem-midi-local.git`.
2. Pasang **Python 3.10 x64** dari https://www.python.org/downloads/windows/ (Python Launcher/`py` juga), atau pasang **uv** lewat `winget install --id astral-sh.uv -e`. Dengan uv, installer mengunduh Python 3.10 secara otomatis. Jangan gunakan Python 3.12 untuk environment proyek ini.
3. Update driver NVIDIA. Jalankan **Install.bat**. Installer membuat `.venv`, memasang PyTorch/Torchaudio 2.5.1 CUDA 12.1, dependensi dan menjalankan tes. CUDA Toolkit terpisah tidak diperlukan oleh wheel ini. Siapkan beberapa GB untuk unduhan dan environment; ruang hasil WAV bertambah sesuai durasi/jumlah stem.
4. Jalankan **Start.bat**. Tunggu backend siap; GitHub Pages akan dibuka dengan token pairing pada URL fragment. Token segera dihapus dari bilah alamat oleh frontend. Token tidak dikirim ke GitHub sebagai query parameter dan tidak disimpan di browser setelah tab ditutup.
5. Izinkan **Local network access / akses jaringan lokal** bila browser meminta. Pilih file, coba **30 detik**, lalu **Pisahkan instrumen**.
6. Dengarkan hasil dan klik **Buat MIDI** pada stem pilihan. Piano menggunakan Transkun secara default; gitar, bass, vokal dan `other` memakai Basic Pitch. `Other` bisa berisi banyak instrumen sekaligus dan lebih rentan salah.
7. Unduh WAV/MIDI/CSV satu per satu atau ZIP. Jendela backend harus tetap terbuka. Ctrl+C menghentikan backend. Jangan matikan di tengah job jika ingin proses selesai.

FFmpeg disediakan oleh `imageio-ffmpeg`, tidak perlu instalasi sistem terpisah. File diproses lokal, tanpa API key dan tanpa kredit inference. Internet diperlukan saat instalasi dan unduhan bobot Demucs pertama kali.

### Bila koneksi Pages → PC diblokir

Gunakan browser desktop terbaru dan izinkan akses jaringan lokal untuk situs. Beberapa browser/kebijakan kantor membatasi permintaan HTTPS ke HTTP loopback; header CORS/PNA tidak dapat memaksa browser memberi izin. Launcher juga menampilkan tautan **versi lokal** dengan UI yang sama. Jangan mematikan keamanan browser, membuka port router, atau mengekspos backend ke internet. GitHub Pages dan backend harus dibuka pada **PC yang sama**; `127.0.0.1` dari HP menunjuk HP itu sendiri.

### GPU dan memori

Target konfigurasi: RTX 4060 8 GB; mode CUDA memakai potongan Demucs 5 detik, satu proses AI pada satu waktu. GTX 1080 juga didukung oleh jalur PyTorch CUDA yang dipilih, tetapi kompatibilitas driver dan hasil inference tetap perlu diuji. Basic Pitch ONNX berjalan di CPU; Demucs/Transkun memakai perangkat pilihan. GPU kehabisan memori: pilih CPU dan kirim ulang cuplikan; tidak ada fallback diam-diam. GPU lokal pengembang yang terdeteksi saat pembuatan adalah **GTX 1080 8 GB**, bukan RTX 4060. Lihat `docs/VALIDATION.md` untuk hasil pengujian yang benar-benar dilakukan.

## Model gratis dan bobot

| Tugas | Model | Sumber bobot | Batas utama |
|---|---|---|---|
| 6 stem | Demucs `htdemucs_6s` | Diunduh otomatis oleh Demucs dari registry upstream | Drums, bass, other, vocals, guitar, piano. Piano eksperimental dan rentan bleed/artifact. |
| 4 stem | Demucs `htdemucs_ft` | Registry upstream Demucs; ensemble beberapa checkpoint | Drums, bass, other, vocals. Tidak memisahkan piano/gitar sendiri. Lebih lambat. |
| MIDI piano | Transkun 2.0.1 / checkpoint `2.0.pt` + config `2.0.conf` | Bundled dalam paket upstream `transkun` | Dilatih untuk piano; stem yang tercemar menurunkan kualitas. |
| MIDI bernada | Basic Pitch 0.4.0 / ICASSP 2022 ONNX | Bundled dalam paket upstream `basic-pitch` | Lebih cocok satu instrumen per input; polifoni, efek dan instrumen tumpang-tindih sulit. |

Ini pilihan gratis yang praktis dan bisa dijalankan lokal, **bukan klaim model terbaik untuk setiap lagu**. `htdemucs_ft` tidak membuat 6 stem. Menjalankan model spesialis lain untuk piano hanya layak ditambahkan setelah perbandingan pada rekaman/sampel pengguna. Tidak ada janji semua instrumen orkestra dapat dipisahkan.

Lihat [MODEL_NOTICES.md](MODEL_NOTICES.md) untuk sumber/lisensi. Checkpoint tidak disalin ke repo. Download model membutuhkan internet dan tunduk pada ketentuan upstream; kode berlisensi terbuka tidak otomatis mengubah hak cipta audio input maupun status output.

## Pengaturan dan hasil

- Pilihan durasi: 30 detik, 60 detik, atau sampai akhir dari waktu mulai, maksimum 30 menit. Upload maksimum 300 MiB. File yang lebih panjang dari batas ditolak pada mode sampai akhir; gunakan cuplikan.
- Mode lebih teliti memakai 2 shifts Demucs, seimbang 1 shift. Tambahan waktu proses tidak menjamin peningkatan di setiap lagu. Angka persentase/ETA tidak dikarang; UI menampilkan tahap dan antrean.
- Onset threshold hanya mengubah Basic Pitch. Durasi minimum not berlaku juga sebagai filter pascaproses Transkun. Penyaringan dapat menghapus not asli yang pendek. MIDI kosong adalah hasil yang mungkin; UI menampilkan jumlah not sebenarnya.
- MIDI dimulai dari detik 0 cuplikan; `start` asli tercatat pada metadata job/ZIP. Timing tidak dikuantisasi, tidak ada deteksi BPM/time signature, MIDI bukan partitur dan tidak mempertahankan suara instrumen asli. Program GM hanyalah label timbre.
- Drum: WAV saja. Vokal: MIDI merepresentasikan pitch, bukan lirik. Piano roll: pemeriksaan visual. Tidak ada editor not manual pada versi pertama.
- `.local/<job-id>/`: sumber, `input.wav`, stem, MIDI/CSV/JSON, `process.log`, metadata dan ZIP. `.local/token.txt`: rahasia pairing. Semuanya diabaikan Git. Hapus folder job secara manual **saat backend berhenti** bila tidak diperlukan; tidak ada penghapusan otomatis audio pengguna.
- Antrean maksimum 3 job termasuk upload. Satu worker, agar model tidak berebut VRAM. Riwayat tetap ada setelah restart; proses yang terputus ditandai error. Unggah ulang untuk mengulang pemisahan. MIDI dapat dicoba ulang pada stem yang sudah tersedia. MIDI lama dipertahankan jika retry gagal.

## Pengembangan dan pengujian

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check frontend/app.js
.\.venv\Scripts\python.exe scripts/smoke_models.py --device cuda
```

Tes unit menjalankan decoder FFmpeg pada WAV buatan, tetapi memalsukan inference model untuk memeriksa autentikasi, CORS, antrean, validasi, ekspor, dan hasil yang tetap tersedia setelah error. `smoke_models.py` terpisah menjalankan **inference sungguhan**: pemisahan 6 stem, Basic Pitch, Transkun pada input bersih dan piano stem, dan validasi MIDI. Sampelnya melodi harmonik sintetis 6 detik, sehingga ini pemeriksaan integrasi, **bukan benchmark akurasi pada lagu**. Model download pertama bisa lama. Log dan report ada di `.local/smoke`.

Untuk menilai akurasi musik: gunakan rekaman instrumen terpisah yang punya MIDI ground truth, campurkan, lalu bandingkan hasil separation dan note onset/offset/pitch terhadap sumber. Belum ada skor akurasi musik nyata sampai dataset itu benar-benar diuji. Dengarkan khusus piano pedal, gitar distorsi, reverb dan akor rapat.

## Keamanan lokal

Backend hanya bind ke loopback. API membutuhkan bearer token, origin diizinkan terbatas dan nama file unduhan memakai allowlist hasil job. CORS bukan autentikasi; token tetap wajib. Token hanya ditampilkan lokal dan tidak boleh dibagikan atau dimasukkan commit. Audio tidak dikirim ke inference cloud. Log GitHub Pages tidak menerima audio, tetapi GitHub tetap melayani kunjungan website seperti biasa. Model Torch hanya dimuat dari paket/registry upstream; tidak ada upload checkpoint dari pengguna. Token dapat diganti dengan menghapus `.local/token.txt` **saat backend berhenti**, lalu jalankan ulang.

## Publikasi GitHub Pages

Workflow `.github/workflows/pages.yml` menerbitkan **hanya `frontend/`**. Atur Settings → Pages → Source: **GitHub Actions**. Backend/weights/data tidak diunggah sebagai artefak Pages. Jika fork ke akun/repo lain, ubah alamat Pages dalam `scripts/launch.py`, tautan repo pada frontend dan origin pada `backend/app.py`.

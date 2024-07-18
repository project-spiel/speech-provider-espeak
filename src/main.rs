use async_io::block_on;
use espeakng_sys::*;
use inotify::{Inotify, WatchMask};
use lazy_static::lazy_static;
use speechprovider::*;
use std::collections::HashSet;
use std::env::current_exe;
use std::ffi::{c_void, CStr, CString};
use std::future::pending;
use std::os::fd::IntoRawFd;
use std::os::raw::{c_int, c_short};
use std::process::exit;
use std::ptr::{addr_of_mut, null, null_mut};
use std::sync::{Mutex, MutexGuard};
use std::thread;
use zbus::{dbus_interface, Connection, ConnectionBuilder, MessageHeader, Result, SignalContext};
use zvariant::OwnedFd;
use oxilangtag::LanguageTag;

const NORMAL_RATE: f32 = 175.0;

lazy_static! {
    static ref ESPEAK_INIT: Mutex<u32> = Mutex::new(0);
}

fn get_voices_path() -> std::path::PathBuf {
    let mut c_voice_path: *const libc::c_char = std::ptr::null();

    unsafe {
        espeak_Info(std::ptr::addr_of_mut!(c_voice_path));
    }

    let cstr = unsafe { CStr::from_ptr(c_voice_path) };
    let path_str = String::from(cstr.to_str().unwrap());
    let mut voices_path = std::path::PathBuf::from(path_str);
    voices_path.push("voices");
    voices_path.push("!v");
    voices_path
}

async fn observe_voices_changed(conn: Connection) {
    let object_server = conn.object_server();
    let speaker_iface_ref = object_server
        .interface::<_, Speaker>("/org/espeak/Speech/Provider")
        .await
        .unwrap();

    thread::spawn(move || {
        let voices_path = get_voices_path();
        let mut inotify = Inotify::init().expect("Error while initializing inotify instance");

        // Watch for modify and close events.
        inotify
            .watches()
            .add(
                voices_path,
                WatchMask::CREATE | WatchMask::DELETE | WatchMask::MOVED_FROM | WatchMask::MOVED_TO,
            )
            .expect("Failed to add file watch");

        let mut buffer = [0; 1024];

        loop {
            inotify
                .read_events_blocking(&mut buffer)
                .expect("Error while reading events");

            block_on(async {
                let speaker_iface = speaker_iface_ref.get_mut().await;
                speaker_iface
                    .voices_changed(speaker_iface_ref.signal_context())
                    .await
            })
            .unwrap();
        }
    });
}

fn observe_uninstall() {
    thread::spawn(move || {
        let me = current_exe().unwrap();
        let mut inotify = Inotify::init().expect("Error while initializing inotify instance");

        // Watch for modify and close events.
        inotify
            .watches()
            .add(me, WatchMask::ALL_EVENTS)
            .expect("Failed to add file watch");

        let mut buffer = [0; 1024];

        loop {
            inotify
                .read_events_blocking(&mut buffer)
                .expect("Error while reading events");

            // Our own executable is gone, we got uninstalled!
            exit(1);
        }
    });
}

trait PoisonlessLock<T> {
    fn plock(&self) -> MutexGuard<T>;
}

impl<T> PoisonlessLock<T> for Mutex<T> {
    fn plock(&self) -> MutexGuard<T> {
        match self.lock() {
            Ok(l) => l,
            Err(e) => e.into_inner(),
        }
    }
}

fn empty_voice() -> espeak_VOICE {
    espeak_VOICE {
        name: null(),
        languages: null(),
        identifier: null(),
        gender: 0,
        age: 0,
        variant: 0,
        xx1: 0,
        score: 0,
        spare: null_mut(),
    }
}

struct StreamWriterWrapper {
    stream_writer: StreamWriter,
    bytes_sent: usize,
}

impl StreamWriterWrapper {
    fn new(fd: OwnedFd) -> StreamWriterWrapper {
        let stream_writer = StreamWriter::new(fd.into_raw_fd());
        stream_writer.send_stream_header();
        StreamWriterWrapper {
            stream_writer,
            bytes_sent: 0,
        }
    }

    fn from_ptr(ptr: *mut c_void) -> &'static mut Self {
        unsafe { &mut *(ptr as *mut Self) }
    }

    fn to_ptr(&mut self) -> *mut c_void {
        self as *mut _ as *mut c_void
    }

    fn send_audio(&mut self, chunk: &[u8]) {
        self.bytes_sent += chunk.len();
        self.stream_writer.send_audio(chunk);
    }

    pub fn send_event(
        &self,
        event_type: EventType,
        range_start: u32,
        range_end: u32,
        mark_name: &str,
    ) {
        self.stream_writer
            .send_event(event_type, range_start, range_end, mark_name);
    }
}

#[allow(non_upper_case_globals)]
extern "C" fn synth_callback(
    wav: *mut c_short,
    sample_count: c_int,
    events: *mut espeak_EVENT,
) -> c_int {
    let stream_writer = StreamWriterWrapper::from_ptr(unsafe { (*events).user_data });
    let wav_slice: &[u8] =
        unsafe { std::slice::from_raw_parts(wav as *const u8, (sample_count * 2) as usize) };
    let mut bytes_sent: usize = 0;

    let mut events_copy = events.clone();
    let sample_rate = unsafe { espeak_ng_GetSampleRate() } as u32;
    let is_mbrola = sample_rate == 16000;
    while unsafe { (*events_copy).type_ != espeak_EVENT_TYPE_espeakEVENT_LIST_TERMINATED } {
        let text_position: usize = unsafe { (*events_copy).text_position.try_into().unwrap() };
        let length: usize = unsafe { (*events_copy).length.try_into().unwrap() };

        let evt = match unsafe { (*events_copy).type_ } {
            espeak_EVENT_TYPE_espeakEVENT_WORD => {
                Some((EventType::Word, text_position, text_position + length))
            }
            espeak_EVENT_TYPE_espeakEVENT_SENTENCE => {
                Some((EventType::Sentence, text_position, text_position + length))
            }
            _ => None,
        };

        if !is_mbrola {
            if let Some((evt_type, start, end)) = evt {
                let audio_position: u32 =
                    unsafe { (*events_copy).audio_position.try_into().unwrap() };
                let mut at_byte: usize = (audio_position * sample_rate / 1000 * 2)
                    .try_into()
                    .unwrap();
                at_byte = at_byte.saturating_sub(stream_writer.bytes_sent);

                if at_byte > 0 {
                    let wav_slice_to_send = &wav_slice[bytes_sent..at_byte];
                    if !wav_slice_to_send.is_empty() {
                        stream_writer.send_audio(wav_slice_to_send);
                        bytes_sent = at_byte;
                    }
                }
                stream_writer.send_event(
                    evt_type,
                    start.saturating_sub(1) as u32,
                    end.saturating_sub(1) as u32,
                    "",
                );
            }
        }

        events_copy = events_copy.wrapping_add(1);
    }

    let wav_slice_to_send = &wav_slice[bytes_sent..];
    if !wav_slice_to_send.is_empty() {
        stream_writer.send_audio(wav_slice_to_send);
    }
    return 0;
}

struct Speaker {}

impl Speaker {
    fn new() -> Speaker {
        let speaker = Speaker {};
        speaker.init();
        speaker
    }
}

#[dbus_interface(name = "org.freedesktop.Speech.Provider")]
impl Speaker {
    fn init(&self) {
        let _lock = ESPEAK_INIT.plock();
        unsafe {
            espeak_Initialize(
                espeak_AUDIO_OUTPUT_AUDIO_OUTPUT_SYNCHRONOUS,
                0,
                std::ptr::null(),
                0,
            );
        };
    }

    #[dbus_interface(property)]
    async fn name(&self) -> String {
        "eSpeak NG".to_string()
    }

    #[dbus_interface(property)]
    async fn voices(&self) -> Vec<(String, String, String, u64, Vec<String>)> {
        let _lock = ESPEAK_INIT.plock();
        let mut langs_hash = HashSet::new();
        let mut voice_arr = unsafe { espeak_ListVoices(null_mut()) };
        while unsafe { !(*voice_arr).is_null() } {
            let voice = unsafe { **voice_arr };
            if !voice.languages.is_null() {
                let mut langs_ptr = voice.languages;
                while unsafe { *langs_ptr != 0 } {
                    // skip priority byte
                    langs_ptr = langs_ptr.wrapping_add(1);
                    let lang_cstr = unsafe { CStr::from_ptr(langs_ptr) };
                    let mut name = String::from(lang_cstr.to_str().unwrap());
                    langs_ptr = langs_ptr.wrapping_add(name.bytes().count() + 1);
                    name = String::from(match LanguageTag::parse_and_normalize(&name) {
                        Ok(lang_tag) => String::from(lang_tag.as_str()),
                        Err(_) => name
                    });
                    langs_hash.insert(name);
                }
            }
            voice_arr = voice_arr.wrapping_add(1);
        }
        let mut langs = langs_hash.into_iter().collect::<Vec<String>>();
        langs.sort();

        let mut features = VoiceFeature::EVENTS_WORD
            | VoiceFeature::EVENTS_SENTENCE
            | VoiceFeature::SSML_SAY_AS_TELEPHONE
            | VoiceFeature::SSML_SAY_AS_CHARACTERS
            | VoiceFeature::SSML_SAY_AS_CHARACTERS_GLYPHS
            | VoiceFeature::SSML_BREAK
            | VoiceFeature::SSML_SUB
            | VoiceFeature::SSML_EMPHASIS
            | VoiceFeature::SSML_PROSODY
            | VoiceFeature::SSML_SENTENCE_PARAGRAPH;

        let mut voice = empty_voice();
        let mut c_lang = CString::new("variant").unwrap();
        voice.languages = c_lang.as_ptr();

        let mut sample_rate = unsafe { espeak_ng_GetSampleRate() } as u32;
        let mut voices = Vec::new();
        voice_arr = unsafe { espeak_ListVoices(addr_of_mut!(voice)) };
        while unsafe { !(*voice_arr).is_null() } {
            let voice = unsafe { **voice_arr };
            if !voice.name.is_null() && !voice.identifier.is_null() {
                let name_cstr = unsafe { CStr::from_ptr(voice.name) };
                let id_cstr = unsafe { CStr::from_ptr(voice.identifier) };
                let audio_format =
                    format!("audio/x-spiel,format=S16LE,channels=1,rate={sample_rate}");
                voices.push((
                    String::from(name_cstr.to_str().unwrap()),
                    String::from(id_cstr.to_str().unwrap().trim_start_matches("!v/")),
                    audio_format,
                    features.bits() as u64,
                    langs.clone(),
                ));
            }
            voice_arr = voice_arr.wrapping_add(1);
        }

        features = VoiceFeature::SSML_SAY_AS_TELEPHONE
        | VoiceFeature::SSML_SAY_AS_CHARACTERS
        | VoiceFeature::SSML_SAY_AS_CHARACTERS_GLYPHS
        | VoiceFeature::SSML_BREAK
        | VoiceFeature::SSML_SUB
        | VoiceFeature::SSML_EMPHASIS
        | VoiceFeature::SSML_PROSODY
        | VoiceFeature::SSML_SENTENCE_PARAGRAPH;

        c_lang = CString::new("mb").unwrap();
        voice.languages = c_lang.as_ptr();

        voice_arr = unsafe { espeak_ListVoices(addr_of_mut!(voice)) };
        // XXX: MBROLA voices are 16 hz.
        sample_rate = 16000;
        while unsafe { !(*voice_arr).is_null() } {
            let voice = unsafe { **voice_arr };
            if !voice.name.is_null() && !voice.identifier.is_null() {
                let name_cstr = unsafe { CStr::from_ptr(voice.name) };
                let id_cstr = unsafe { CStr::from_ptr(voice.identifier) };
                let audio_format =
                    format!("audio/x-spiel,format=S16LE,channels=1,rate={sample_rate}");
                voices.push((
                    String::from(name_cstr.to_str().unwrap()),
                    String::from(id_cstr.to_str().unwrap().trim_start_matches("!v/")),
                    audio_format,
                    features.bits() as u64,
                    langs.clone(),
                ));
            }
            voice_arr = voice_arr.wrapping_add(1);
        }

        voices
    }

    async fn synthesize(
        &mut self,
        fd: OwnedFd,
        utterance: &str,
        voice_id: &str,
        pitch: f32,
        rate: f32,
        is_ssml: bool,
        language: &str,
        #[zbus(header)] _header: MessageHeader<'_>,
        #[zbus(signal_context)] _ctxt: SignalContext<'_>,
    ) {
        let utterance_cstr = CString::new(utterance).unwrap();

        let voice_name = if voice_id.starts_with("mb/") {
            String::from(voice_id)
        } else if language.is_empty() {
            let default_voice_utf8 = &ESPEAKNG_DEFAULT_VOICE[..ESPEAKNG_DEFAULT_VOICE.len() - 1];
            let default_voice = std::str::from_utf8(default_voice_utf8).unwrap();
            format!("{default_voice}+{voice_id}")
        } else {
            format!("{language}+{voice_id}")
        };

        thread::spawn(move || {
            let position = 0u32;
            let position_type: espeak_POSITION_TYPE = 0;
            let end_position = 0u32;
            let flags = if is_ssml {
                espeakSSML | espeakCHARS_AUTO
            } else {
                espeakCHARS_AUTO
            };
            let mut stream_writer = StreamWriterWrapper::new(fd);
            let stream_writer_ptr = stream_writer.to_ptr();

            let c_lang = CString::new(voice_name).unwrap();

            unsafe {
                let _lock = ESPEAK_INIT.plock();
                espeak_SetSynthCallback(Some(synth_callback));
                espeak_SetVoiceByName(c_lang.as_ptr());
                espeak_SetParameter(
                    espeak_PARAMETER_espeakPITCH,
                    (pitch * 50.0).round() as i32,
                    0,
                );
                espeak_SetParameter(
                    espeak_PARAMETER_espeakRATE,
                    (rate * NORMAL_RATE).round() as i32,
                    0,
                );
                espeak_Synth(
                    utterance_cstr.as_ptr() as *const c_void,
                    500,
                    position,
                    position_type,
                    end_position,
                    flags,
                    null_mut(),
                    stream_writer_ptr,
                );
            }
        });
    }
}

// Although we use `async-std` here, you can use any async runtime of choice.
#[async_std::main]
async fn main() -> Result<()> {
    let conn = ConnectionBuilder::session()?
        .name("org.espeak.Speech.Provider")?
        .serve_at("/org/espeak/Speech/Provider", Speaker::new())?
        .build()
        .await?;

    observe_voices_changed(conn).await;

    observe_uninstall();

    pending::<()>().await;

    Ok(())
}

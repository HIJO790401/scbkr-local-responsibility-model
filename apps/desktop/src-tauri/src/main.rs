fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running SCBKR P14-B desktop skeleton");
}

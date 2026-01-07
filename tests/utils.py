import copy
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from malas.crews.models.TaskOutput import Makalah, ReferenceItem
from docxtpl import DocxTemplate
from jinja2 import Environment
import os
from datetime import datetime

HARCODED_DATA = {
    "judul": "MODEL PEMBELAJARAN FIQIH TENTANG WARIS",
    "mata_kuliah": "Pembelajaran Fiqih",
    "dosen_pengampu": "Dr. Hj. Salsabilah, M.Ag",
    "penyusun": [
        {"nama": "Silvie Ghaitsa Salsabila", "nim": "1222020283"},
        {"nama": "Syahrul Gunawan", "nim": "1222020294"},
        {"nama": "Umi Sakinatunnuha", "nim": "1222020283"}
    ],
    "kelas": "C",
    "universitas": "UNIVERSITAS ISLAM NEGERI SUNAN GUNUNG DJATI",
    "fakultas": "FAKULTAS TARBIYAH DAN KEGURUAN",
    "jurusan": "JURUSAN PENDIDIKAN AGAMA ISLAM",
    "kota": "Bandung",
    "tahun": "2024",

    "kata_pengantar": """Segala puji serta syukur selalu dipanjatkan kehadirat Allah SWT yang telah memberikan taufiq dan hidayah-Nya. Tak lupa sholawat serta salam juga selalu tercurah limpahkan kepada junjungan Nabi Muhammad SAW, kepada para sahabatnya, dan kita selaku umatnya. Sehingga kami dapat menyelesaikan makalah ini yang berjudul “Sejarah Penulisan dan Pembukuan Hadist” dengan tepat waktu. Makalah ini ditulis dengan tujuan untuk sama-sama belajar dan memberikan pemahaman yang lebih baik tentang sejarah penulisan dan pembukuan hadist.
    Kami berharap makalah ini dapat memberikan informasi dan pemikiran yang berguna bagi pembaca untuk menambah pengetahuan mereka mengenai hadist. Dalam penyusunan makalah ini, kami memperoleh banyak bantuan dan dukungan dari berbagai pihak. Oleh karena itu, kami ingin mengucapkan terima kasih kepada semua pihak yang telah memberikan dukungan dan motivasi dalam proses penyusunan makalah ini. Kami juga ingin mengucapkan terima kasih kepada dosen pengampu yaitu Ibu Dr. Dadah, M.Ag. yang telah memberikan arahan dan bimbingan dalam penyusunan makalah ini. Kami tidak akan bisa menyelesaikan makalah ini tanpa bantuan dan bimbingan beliau. Akhir kata, kami berharap makalah ini dapat memberikan manfaat dan kontribusi bagi ilmu pengetahuan dan pembaca. Terima kasih.
""",

    "bab": {
       "I": {
            "judul": "Pendahuluan",
            "subbab": [
                {
                    "judul": "1.1 Latar Belakang",
                    "content": [
                        {
                            "type": "text",
                            "isi": "Ini adalah paragraf pengantar dummy untuk 1.1 Latar Belakang. Teks ini menjelaskan konteks umum dari topik yang akan dibahas secara naratif."
                        },
                    ]
                },
                {
                    "judul": "1.2 Rumusan Masalah",
                    "content": [
                        {
                            "type": "list",
                            "title_items": "Berikut adalah poin-poin utama permasalahan:",
                            "items": [
                                "Poin pertama yang mengidentifikasi celah penelitian.",
                                "Poin kedua yang menyoroti urgensi dari masalah.",
                                "Poin ketiga yang berkaitan dengan dampak praktis."
                            ]
                        },
                    ]
                },
                {
                    "judul": "1.3 Tujuan Penulisan",
                    "content": [
                        {
                            "type": "list",
                            "title_items": "Berikut adalah poin-poin utama permasalahan:",
                            "items": [
                                "Poin pertama yang mengidentifikasi celah penelitian.",
                                "Poin kedua yang menyoroti urgensi dari masalah.",
                                "Poin ketiga yang berkaitan dengan dampak praktis."
                            ]
                        },
                    ]
                }
            ]
        },
        "II": {
            "judul": "PEMBAHASAN",
            "subbab": [
                {
                    "judul": "Pengertian Waris dan Rukun-rukun Warisan",
                    "content": [
                        {"type": "text", "isi": """Waris dalam bahasa Arab memiliki arti "pengganti" atau "yang mewarisi". Istilah ini merujuk pada seseorang yang menerima harta benda dari orang yang telah meninggal dunia. Dalam istilah hukum Islam, "waris" didefinisikan sebagai perpindahan hak kepemilikan atas harta benda dari seseorang yang telah meninggal dunia (al-muwaris) kepada ahli warisnya yang masih hidup. Hukum waris dalam Islam mengatur bagaimana harta benda dibagikan kepada para ahli waris berdasarkan hubungan keluarga dan ketentuan yang ditetapkan dalam Al-Qur'an dan Hadits.
Hukum waris dalam Islam didasarkan pada Al-Qur'an, Hadits, dan ijma' para ulama.  Al-Qur'an sendiri secara tegas mengatur tentang pembagian warisan dalam beberapa surat, seperti surat An-Nisa' ayat 11-12, surat Al-Baqarah ayat 180, dan surat Al-Maidah ayat 106. Terjemahan surat An-Nisa ayat 11-12 tentang warisan:
“Allah mensyari’atkan kepadamu tentang (pembagian warisan untuk) anak-anakmu, yaitu bagian seorang anak laki-laki sama dengan bagian dua orang anak perempuan. Dan jika anak itu semuanya perempuan yang jumlahnya lebih dari dua, maka bagian mereka dua pertiga dari harta yang ditinggalkan. Jika anak perempuan itu seorang saja, maka dia memperoleh setengah (harta yang ditinggalkan). Dan untuk kedua ibu-bapak, bagian masing-masing seperenam dari harta yang ditinggalkan, jika yang meninggal itu mempunyai anak. Jika orang yang meninggal tidak mempunyai anak dan dia diwarisi oleh kedua ibu-bapaknya (saja), maka ibunya mendapat sepertiga. Jika yang meninggal itu mempunyai beberapa saudara, maka ibunya mendapat seperenam. (Pembagian-pembagian tersebut di atas) setelah dipenuhi wasiat yang dibuatnya atau (dan) setelah dibayar hutangnya. (Tentang) orang tuamu dan anak-anakmu, kamu tidak mengetahui siapa di antara mereka yang lebih banyak manfaatnya bagimu. Ini adalah ketetapan Allah. Sungguh, Allah Maha Mengetahui lagi Mahabijaksana.”
 “Dan bagianmu (suami-suami) adalah seperdua dari harta yang ditinggalkan oleh isteri-isterimu, jika mereka tidak mempunyai anak. Jika mereka (istri-istrimu) itu mempunyai anak, maka kamu mendapat seperempat dari harta yang ditinggalkannya setelah dipenuhi wasiat yang mereka buat atau (dan) setelah dibayar hutangnya. Para isteri memperoleh seperempat harta yang kamu tinggalkan jika kamu tidak mempunyai anak. Jika kamu mempunyai anak, maka para isteri memperoleh seperdelapan dari harta yang kamu tinggalkan setelah dipenuhi wasiat yang kamu buat atau (dan) setelah dibayar hutang-hutangmu. Jika seseorang meninggal, baik laki-laki maupun perempuan yang tidak meninggalkan ayah dan tidak meninggalkan anak, tetapi mempunyai seorang saudara laki-laki (seibu) atau seorang saudara perempuan (seibu), maka bagi masing-masing dari kedua jenis saudara itu seperenam harta. Tetapi jika saudara-saudara seibu itu lebih dari seorang, maka mereka bersama-sama dalam bagian yang sepertiga itu, setelah dipenuhi wasiat yang dibuatnya atau (dan) setelah dibayar hutangnya dengan tidak menyusahkan (kepada ahli waris). Demikianlah ketentuan Allah. Allah Maha Mengetahui lagi Maha Penyantun.”
"""},
                                {"type": "list","title_items" : "Rukun-rukun warisan" ,"items": [
                            "Al-Muwaris (Pewaris): Orang yang meninggal dunia dan meninggalkan harta warisan.  ",
                            "Al-Waris (Ahli Waris): Orang yang berhak menerima warisan berdasarkan ketentuan hukum Islam.  ",
                            "Al-Mirats (Harta Warisan): Harta benda yang ditinggalkan oleh al-muwaris."
                        ]}
                    ]
                },
                {
                    "judul": "Jenis-jenis Warisan",
                    "content": [
                        {"type": "text", "isi": "Harta warisan adalah harta kekayaan yang ditinggalkan oleh seseorang setelah meninggal dunia. Menurut Badan Pembinaan Hukum Nasional (BPHN) Kemenkumham RI, harta warisan adalah harta berupa hak dan kewajiban yang dapat dinilai dengan uang. Dalam hal ini, harta warisan merupakan harta peninggalan yang diberikan kepada ahli waris atau keluarga yang bersangkutan ketika seseorang meninggal. Pembagian harta warisan biasanya didasarkan pada hubungan darah, pernikahan, persaudaraan, hingga hubungan kerabat. Berikut beberapa jenis harta warisan:"},
                        {"type": "list","title_items" : "TESTING" ,"items": [
                            "Harta bergerak: Harta bergerak adalah aset yang dapat dipindahkan dari satu tempat ke tempat lain. Contohnya uang tunai, perhiasan, kendaraan (mobil, motor, dll.), barang elektronik, koleksi pribadi (lukisan, koin, prangko, dll).",
                            "Harta tidak bergerak: Harta tidak bergerak adalah aset yang tidak bisa dipindahkan dan biasanya memiliki nilai yang cukup besar. Contohnya tanah, bangunan (rumah, apartemen, ruko, dll.), properti komersial (toko, kantor, dll).",
                            "Harta Kekayaan Finansial: Harta ini meliputi instrumen keuangan yang dimiliki oleh almarhum. Contohnya saham, obligasi, rekening bank, deposito, reksadana, asuransi jiwa."
                            "Harta Digital: Dengan kemajuan teknologi, harta digital juga menjadi bagian dari warisan. Ini termasuk akun media sosial, konten digital (musik, film, buku elektronik), dompet digital atau cryptocurrency, nama domain dan situs web.",
                        ]},
                        {"type": "text", "isi": "Di Indonesia, ada tiga jenis hukum waris yang digunakan, yaitu hukum waris Islam, hukum waris adat, dan hukum perdata. Sistem hukum yang digunakan tergantung pada pengaruh agama, kelompok masyarakat, dan pilihan sistem hukum yang akan diterapkan."}
                    ]
                },
                {
                    "judul": "Hak dan Kewajiban Ahli Waris",
                    "content": [
                        {"type": "text", "isi": "Setiap ahli waris memiliki hak dan tanggung jawab terhadap harta warisan yang diterimanya. Hak ahli waris adalah memperoleh bagian dari harta tersebut. Namun, ahli waris juga memiliki sejumlah kewajiban, seperti menanggung biaya perawatan jenazah dan melunasi hutang-hutang pewaris. Dengan kata lain, sebelum warisan dibagikan, terlebih dahulu harus diselesaikan berbagai kewajiban yang berkaitan dengan harta peninggalan tersebut. Adapun hak-hak yang harus diselesaikan oleh ahli waris adalah:"},
                        {"type": "list","title_items" : None ,"items": [
                            "Zakat: Jika sudah tiba waktunya untuk membayar zakat, maka hal ini harus dilakukan terlebih dahulu.",
                            "Harta tidak bergerak: Harta tidak bergerak adalah aset yang tidak bisa dipindahkan dan biasanya memiliki nilai yang cukup besar. Contohnya tanah, bangunan (rumah, apartemen, ruko, dll.), properti komersial (toko, kantor, dll).",
                            "Belanja: Yaitu biaya yang diperlukan untuk penyelenggaraan dan pengurusan jenazah, seperti biaya kain kafan, upah untuk menggali kubur, dan hal-hal lain yang terkait.",
                            "c.\tHutang: Jika almarhum memiliki hutang, maka hutang tersebut harus dilunasi terlebih dahulu.",
                            """Wasiat: Jika mayat itu ada meninggalkan pesan (wasiat), agar sebagian dari harta peninggalannya diberikan kepada seseorang, maka wasiat ini pun harus dilaksanakan. Allah Swt. berfirman dalam Al-Qur'an:
مِنۡۢ بَعۡدِ وَصِيَّةٍ يُّوۡصِىۡ بِهَاۤ اَوۡ دَيۡنٍ‌
Artinya: "(Pembagian-pembagian tersebut di atas) setelah (dipenuhi) wasiat yang dibuatnya atau (dan setelah dibayar) hutangnya." (An-Nisa' : 11)
""",
                        ]},
                        {"type": "text", "isi": "Di Indonesia, ada tiga jenis hukum waris yang digunakan, yaitu hukum waris Islam, hukum waris adat, dan hukum perdata. Sistem hukum yang digunakan tergantung pada pengaruh agama, kelompok masyarakat, dan pilihan sistem hukum yang akan diterapkan."}
                    ]
                }
            ]
        },
        "III": {
            "judul": "Bab 3",
            "subbab": [
                {
                    "judul": "3.1 Kesimpulan",
                    "content": [
                        {
                            "type": "text",
                            "isi": "Ini adalah paragraf pengantar dummy untuk 3.1 Kesimpulan. Teks ini menjelaskan konteks umum dari topik yang akan dibahas secara naratif."
                        },
                        {
                            "type": "text",
                            "isi": "Paragraf penutup ini menyimpulkan poin-poin di atas dan mengarahkan pembaca ke bagian selanjutnya dari makalah."
                        }
                    ]
                }
            ],
            "kesimpulan": ''
        }
    },

    "daftar_pustaka": [
        "Bangun, Erni. (2017). Pembatalan atas Pembagian Harta Warisan Menurut KUHPerdata. Lex et Societatis, 5(1).",
        "Hasan, M. Ali. (1979). Hukum Warisan dalam Islam. Jakarta: Bulan Bintang.",
        "Prudential Syariah. (n.d.). Apa itu Warisan? Diakses dari https://www.prudentialsyariah.co.id",
        "CIMB Niaga. (n.d.). Fakta Harta Warisan. Diakses dari https://www.cimbniaga.co.id",
        "Sindonews. (n.d.). Tafsir Surat An-Nisa Ayat 11. Diakses dari https://kalam.sindonews.com/ayat/11/4/an-nisa-ayat-11",
        "Mustari, Abdillah. Hukum Kewarisan Islam. Buku Daras UIN Alauddin.",
        "Tirto.id. (n.d.). Syarat dan Rukun Waris dalam Islam. Diakses dari https://tirto.id"
    ]
}

    

def transform_structure(makalah_data, chapter_key="I"):
    """
    Mengubah struktur konten dari satu bab spesifik (default: Bab "I")
    menjadi SimpleNamespace yang ringkas, tanpa menyentuh bab lain.
    """
    # 1. Buat salinan data yang aman untuk diubah
    data_copy = copy.deepcopy(makalah_data)

    # 2. Cek dulu apakah bab yang dituju ada di dalam data
    if "bab" not in data_copy or chapter_key not in data_copy["bab"]:
        print(f"Peringatan: Bab '{chapter_key}' tidak ditemukan. Tidak ada perubahan dilakukan.")
        return data_copy

    # Mapping nama atribut (hanya untuk Bab I)
    key_map = {
        "Latar Belakang": "latar_belakang",
        "Rumusan Masalah": "rumusan_masalah",
        "Tujuan Penulisan": "tujuan"
    }
    
    # 3. Ambil data bab spesifik yang akan diubah
    chapter_dict = data_copy["bab"][chapter_key]
    transformed_chapter = SimpleNamespace()

    # Salin properti utama bab (seperti judul)
    for key, value in chapter_dict.items():
        if key != 'subbab':
            setattr(transformed_chapter, key, value)
            
    # 4. Proses sub-bab dari bab yang ditargetkan ini
    for subbab in chapter_dict.get("subbab", []):
        judul_subbab = subbab.get("judul", "")
        attribute_key = None
        
        for formal_name, attr_name in key_map.items():
            if formal_name in judul_subbab:
                attribute_key = attr_name
                break
        
        if not attribute_key:
            # Fallback jika tidak ada di map
            cleaned_title = ' '.join(judul_subbab.split(' ')[1:])
            attribute_key = cleaned_title.lower().replace(' ', '_').strip()

        # Gabungkan konten menjadi satu string ringkas
        content_parts = []
        for content_item in subbab.get("content", []):
            if content_item.get("type") == "text":
                content_parts.append(content_item.get("isi", ""))
            elif content_item.get("type") == "list":
                if content_item.get("title_items"):
                    content_parts.append(content_item.get("title_items"))
                for item in content_item.get("items", []):
                    content_parts.append(f"- {item}")
        
        final_content = "\n".join(content_parts)
        setattr(transformed_chapter, attribute_key, final_content)

    # 5. Ganti bab lama dengan bab yang sudah ditransformasi di dalam data
    data_copy["bab"][chapter_key] = transformed_chapter
    
    return data_copy

def format_apa7(ref):
    """
    Mengubah sebuah dictionary referensi menjadi string berformat APA 7.

    Args:
        ref (dict): Dictionary yang berisi 'authors', 'year', 'title', dan 'link'.

    Returns:
        str: String referensi yang sudah diformat.
    """
    
    # --- 1. Memformat Nama Penulis ---
    authors_list = ref.get('authors', [])
    formatted_authors = []
    for name in authors_list:
        parts = name.split()
        if not parts:
            continue
        last_name = parts[-1]
        # Membuat inisial dari nama depan/tengah
        initials = " ".join([f"{p[0]}." for p in parts[:-1]])
        formatted_authors.append(f"{last_name}, {initials}")

    # Menggabungkan daftar penulis dengan koma dan ampersand (&)
    num_authors = len(formatted_authors)
    if num_authors == 0:
        authors_str = "Penulis tidak diketahui"
    elif num_authors == 1:
        authors_str = formatted_authors[0]
    elif num_authors == 2:
        authors_str = f"{formatted_authors[0]} & {formatted_authors[1]}"
    else:
        # Gabungkan semua kecuali yang terakhir dengan koma, lalu tambahkan '&'
        authors_str = ", ".join(formatted_authors[:-1]) + f", & {formatted_authors[-1]}"
    
    # --- 2. Memformat Tahun ---
    year = ref.get('year', 'n.d.') # 'n.d.' berarti 'no date'
    year_str = f"({year})."

    # --- 3. Memformat Judul ---
    # APA 7 menggunakan sentence case untuk judul artikel.
    title = ref.get('title', 'Judul tidak diketahui').strip()
    # Ini adalah cara sederhana untuk membuat sentence case
    title_str = title[0].upper() + title[1:] + "."

    # --- 4. Mengambil Link ---
    link = ref.get('link', '')

    # --- 5. Menggabungkan Semua Bagian ---
    # Format: Penulis. (Tahun). Judul artikel. Link
    final_reference = f"{authors_str}. {year_str} {title_str} {link}"
    
    return final_reference





class DocxConverter:
    """
    Utility class to convert a Makalah data object into a formatted .docx document
    using Jinja2 templating and docxtpl.

    Example:
    --------
    converter = DocxConverter("template.docx", "output/makalah.docx")
    converter.convert(makalah_state)
    """

    def __init__(self, template_path: str, output_path: Optional[str] = None, *, hardcoded: bool = False):
        """
        Parameters
        ----------
        template_path : str
            Path to the .docx template file.
        output_path : Optional[str]
            Path to save the rendered .docx file. If not provided, will auto-generate one.
        hardcoded : bool, optional
            Whether to use hardcoded data for rendering (useful for debugging or testing).
        """
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Template not found at: {template_path}")

        self.template_path = template_path
        self.output_path = output_path or self._default_output_path()
        self.hardcoded = hardcoded
        self.jinja_env = Environment(trim_blocks=True, lstrip_blocks=True)


    def _default_output_path(self) -> str:
        """Generate a default output filename with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"makalah_output_{timestamp}.docx"

    def _generate_context(self, makalah_state: Makalah) -> Dict[str, Any]:
        """Prepare the context dictionary for rendering."""
        if self.hardcoded:
            context = HARCODED_DATA
        else:
            context = makalah_state.model_dump(mode='python')

        daftar_pustaka_asli = context.get('daftar_pustaka', [])
        daftar_pustaka_terformat = [format_apa7(ref) for ref in daftar_pustaka_asli]
        context['daftar_pustaka_formatted'] = daftar_pustaka_terformat

        # Tambahkan daftar alfabet untuk enumerasi (a, b, c, ...)
        context["alphabet"] = [chr(ord("a") + i) for i in range(26)]
        return context

    def convert(self, makalah_state: Makalah) -> str:
        """
        Render the makalah into a .docx file.

        Returns
        -------
        str
            The path of the generated .docx file.
        """
        try:
            context = self._generate_context(makalah_state)
            doc = DocxTemplate(self.template_path)
            doc.render(context, jinja_env=self.jinja_env)

            output_dir = os.path.dirname(self.output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            doc.save(self.output_path)

            return self.output_path

        except Exception as e:
            raise
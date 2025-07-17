from utils.requestAIattack import AzureOpenAIChatClient
import numpy as np
import faiss
import pickle
import os

class VectorDatabase:
    def __init__(self,dimension=1536):
        self.dimension = dimension
        self.client = AzureOpenAIChatClient(embedding_deployment="text-embedding-ada-002")
    
    def build_index(self,texts):
        """构建索引咯🎵ダーリング🎵"""
        self.texts = texts
        embeddings = []

        for text in texts:
            embedding = self.client.get_embedding(text)
            embeddings.append(embedding)

        embeddings = np.vstack(embeddings)

        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(embeddings.astype('float32'))

    def search(self,query, k=5):
        """搜索最相近的文本"""
        query_embedding = self.client.get_embedding(query)

        # 搜索最相似的向量
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1).astype('float32'), 
            k
        )
        
        # 返回结果
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            results.append({
                'text': self.texts[idx],
                'distance': dist,
                'rank': i + 1
            })
        
        return results
    
    def save(self, path):
        """保存索引和文本"""
        os.makedirs(path, exist_ok=True)
        faiss.write_index(self.index, f"{path}/index.faiss")
        with open(f"{path}/texts.pkl", 'wb') as f:
            pickle.dump(self.texts, f)

    def load(self, path):
        """加载索引和文本"""
        self.index = faiss.read_index(f"{path}/index.faiss")
        with open(f"{path}/texts.pkl", 'rb') as f:
            self.texts = pickle.load(f)

def main():
    license_info = {
        "Black": {
            "licenses": [
                "SleepyCat",
                "Aladdin Free Public License",
                "Berkeley DB licenses",
                "CC-BY-NC-2.0",
                "CC-BY-NC-SA-2.0", 
                "CC-BY-NC-SA-3.0",
                "CC-BY-NC-SA-4.0"
            ],
            "risk_level": "very high",
            "risk_reason": "nearly unlimited copy left effect",
            "obligations": "Before thinking about components licensed under these license, get in contact with your software clearing experts!"
        },
        "Blue": {
            "licenses": [
                "MIT",
                "BSD (except for BSD-4-Clause)",
                "BSL-1.0",
                "CPOL-1.02",
                "MsPL",
                "zLib",
                "Apache-1.1",
                "Apache-2.0 (if no code changes are done)",
                "APL-1.0",
                "APAFML",
                "ANTLR-PD",
                "AML",
                "Beerware",
                "bzip2-1.0.6",
                "CECILL-B",
                "MIT-CMU",
                "CPAL-1.0",
                "CC-PDDC",
                "CC0-1.0",
                "Cryptogams",
                "curl",
                "WTFPL",
                "EDL-1.0 (=BSD-3-Clause)",
                "EFL-1.0",
                "EFL-2.0",
                "FSAP",
                "FSFUL",
                "FSFULLR",
                "HPND",
                "HTMLTIDY",
                "ICU",
                "Info-ZIP",
                "ISC",
                "JSON",
                "libpng",
                "libpng-2.0",
                "libtiff",
                "NPL-1.0",
                "NTP",
                "OLDAP-2.0.1",
                "OLDAP-2.8",
                "OML",
                "PostGreSQL",
                "Public Domain",
                "SAX-PD",
                "SGI-B-2.0",
                "Spencer-94",
                "Spencer-99",
                "blessing",
                "TCL",
                "Unlicense",
                "UPL-1.0",
                "NCSA",
                "W3C-20150513",
                "X11",
                "zLib"
            ],
            "risk_level": "low",
            "risk_reason": "permissive licenses",
            "obligations": [
                "Display license text",
                "Display copyrights"
            ]
        },
        "Red": {
            "licenses": [
                "GPL-2.0",
                "GPL-3.0", 
                "LGPL-2.1",
                "LGPL-3.0",
                "AGPL",
                "APSL-2.0",
                "Artistic-2.0",
                "eCos-2.0",
                "RHeCos-1.1",
                "SSPL-1.0"
            ],
            "risk_level": "high",
            "risk_reason": "copyleft effect",
            "obligations": [
                "Display license text",
                "Display copyrights",
                "Take care about copyleft effect - get in contact with your software clearing experts",
                "All distributions must clearly state that (L)GPL license code is used"
            ]
        },
        "Yellow": {
            "licenses": [
                "CDDL-1.0",
                "CDDL-1.1",
                "CPL-1.0", 
                "EPL-1.0",
                "eCos License",
                "MPL",
                "NPL",
                "AFL-2.0",
                "AFL-2.1", 
                "AFL-3.0",
                "Artistic-1.0",
                "Artistic1.0-Perl",
                "CC-BY-SA-2.0",
                "CC-BY-SA-3.0",
                "CC-BY-SA-4.0",
                "CECILL-2.0",
                "CECILL-B",
                "CC-BY-2.0",
                "CC-BY-3.0", 
                "CC-BY-4.0",
                "EPL-2.0",
                "ErlPL-1.1",
                "FTL",
                "gnuplot",
                "IPL-1.0",
                "IJG",
                "MS-PL",
                "MS-RL",
                "NASA-1.3",
                "NPL-1.1",
                "ODbL-1.0",
                "OSL-1.1",
                "OpenSSL",
                "PHP-3.0",
                "PHP-3.01",
                "Python-2.0",
                "QHull",
                "RSA-MD",
                "SGI-B-1.1",
                "OFL-1.0",
                "OFL-1.1",
                "SPL-1.0",
                "Unicode-DFS-2015",
                "Unicode-DFS-2016",
                "Unicode-TOU",
                "W3C-19980720",
                "W3C",
                "wxWindows",
                "XFree86-1.1",
                "Zend-2.0",
                "ZPL-2.0",
                "ZPL-2.1"
            ],
            "risk_level": "medium",
            "risk_reason": "limited copyleft effect",
            "obligations": [
                "Display license text",
                "Display copyrights",
                "All changes of the component code must become OSS as well",
                "Possible license incompatibility with red licenses"
            ]
        }
    }

    db = VectorDatabase()
    db.build_index(license_info)
    db.save(r"\database")
    result = db.search("Sleep")
    print(result)

if __name__ == "__main__":
    main()
from typing import List
from datetime import datetime
from pathlib import Path
from .content_types import VectorChunk

class ChunkReportService:
    @staticmethod
    def generate_report(
        chunks: List[VectorChunk],
        output_path: str,
        title: str = "Content Chunking Report"
    ) -> str:
        """
        Generates an HTML report visualizing how content was chunked
        
        Args:
            chunks: List of vector chunks to visualize
            output_path: Where to save the HTML report
            title: Title for the report
            
        Returns:
            Path to the generated HTML file
        """
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{title}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .header {{
                    background-color: #2c3e50;
                    color: white;
                    padding: 20px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .chunk {{
                    background-color: white;
                    padding: 15px;
                    margin-bottom: 15px;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .chunk-text {{
                    white-space: pre-wrap;
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 3px;
                    border-left: 4px solid #3498db;
                }}
                .metadata {{
                    font-size: 0.9em;
                    color: #666;
                    margin-top: 10px;
                    padding-top: 10px;
                    border-top: 1px solid #eee;
                }}
                .metadata-item {{
                    margin: 5px 0;
                }}
                .stats {{
                    background-color: #3498db;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                }}
                .toggle-btn {{
                    background-color: #2c3e50;
                    color: white;
                    border: none;
                    padding: 5px 10px;
                    border-radius: 3px;
                    cursor: pointer;
                    margin-bottom: 10px;
                }}
                .hidden {{
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{title}</h1>
                <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            
            <div class="stats">
                <h2>Chunking Statistics</h2>
                <p>Total Chunks: {len(chunks)}</p>
                <p>Average Chunk Size: {sum(len(c.text) for c in chunks) / len(chunks):.0f} characters</p>
            </div>
            
            <button class="toggle-btn" onclick="toggleAllMetadata()">Toggle All Metadata</button>
            
            <div id="chunks">
        """
        
        # Add each chunk to the report
        for i, chunk in enumerate(chunks, 1):
            html_content += f"""
                <div class="chunk">
                    <h3>Chunk {i}</h3>
                    <div class="chunk-text">{chunk.text}</div>
                    <button class="toggle-btn" onclick="toggleMetadata('metadata-{i}')">
                        Toggle Metadata
                    </button>
                    <div id="metadata-{i}" class="metadata hidden">
                        <div class="metadata-item"><strong>Object ID:</strong> {chunk.object_id}</div>
                        <div class="metadata-item"><strong>User ID:</strong> {chunk.user_id}</div>
                        <div class="metadata-item"><strong>Characters:</strong> {len(chunk.text)}</div>
                        <div class="metadata-item"><strong>Additional Metadata:</strong></div>
                        <pre>{str(chunk.metadata)}</pre>
                    </div>
                </div>
            """
        
        html_content += """
            </div>
            
            <script>
                function toggleMetadata(id) {
                    const element = document.getElementById(id);
                    element.classList.toggle('hidden');
                }
                
                function toggleAllMetadata() {
                    const allMetadata = document.querySelectorAll('.metadata');
                    const allHidden = Array.from(allMetadata).every(el => el.classList.contains('hidden'));
                    
                    allMetadata.forEach(el => {
                        if (allHidden) {
                            el.classList.remove('hidden');
                        } else {
                            el.classList.add('hidden');
                        }
                    });
                }
            </script>
        </body>
        </html>
        """
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write the report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return output_path 
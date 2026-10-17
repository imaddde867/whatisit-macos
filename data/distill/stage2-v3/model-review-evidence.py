import hashlib,json,os,subprocess
from pathlib import Path
root=Path('data/distill/stage2-v3')
env={**os.environ,'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','MANPATH':'/usr/share/man:/Library/Developer/CommandLineTools/usr/share/man','MANWIDTH':'120','LC_ALL':'C'}
manuals={}
for name in ('mdfind','date','system_profiler','osascript','fdesetup','networksetup','printf','nc','cp','find','diskutil','ps','plutil','openssl','xcodebuild','grep','git','stat','mdls','du','iostat','ditto','afinfo','socketfilterfw','hdiutil','defaults','test','PlistBuddy','time'):
 r=subprocess.run(['/usr/bin/man',name],env=env,text=True,capture_output=True)
 text=subprocess.run(['/usr/bin/col','-b'],input=r.stdout,text=True,capture_output=True).stdout
 manuals[name]={'available':r.returncode==0,'rendered_sha256':hashlib.sha256(text.encode()).hexdigest() if text else None}
registry=subprocess.check_output(['/usr/bin/mdimport','-A'],env=env,text=True)
attrs={key:key in registry for key in ('kMDItemAudioChannelCount','kMDItemAudioNumberOfChannels','kMDItemVideoFrameRate','kMDItemISOSpeed','kMDItemWhereFroms','kMDItemAuthors','kMDItemUserTags','kMDItemLastUsedDate','kMDItemFinderComment')}
report={'manuals':manuals,'metadata_registry_sha256':hashlib.sha256(registry.encode()).hexdigest(),'metadata_attributes':attrs,
 'primary_sources':{'query_syntax':'https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/SpotlightQuery/Concepts/QueryFormat.html',
 'video_attributes':'https://developer.apple.com/documentation/coreservices/file_metadata/mditem/video_metadata_attribute_keys',
 'audio_attributes':'https://developer.apple.com/documentation/coreservices/file_metadata/mditem/audio_metadata_attribute_keys'}}
(root/'model-review-evidence.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({'missing_manuals':[k for k,v in manuals.items() if not v['available']], 'metadata_attributes':attrs}))

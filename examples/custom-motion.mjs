// Explicitly invoked local module. Not loaded automatically from project files.
export default async function({project}) {
  project.customTracks ||= {};
  for(const token of project.tokens){
    if(token.start===null||token.end===null)continue;
    project.customTracks[token.id]={
      x:[{time:token.start,value:project.width*.2,interpolation:'hermite',outTangent:900},{time:token.end,value:project.width*.8,inTangent:900}],
      rotation:[{time:token.start,value:-15,interpolation:'linear'},{time:token.end,value:15}]
    };
  }
  return project;
}
